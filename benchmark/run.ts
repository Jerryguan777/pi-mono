/**
 * GAIA Level 2 Benchmark Runner for pi-coding-agent SDK.
 *
 * Usage: npx tsx benchmark/run.ts
 *   --concurrency N    Concurrent tasks (default 3)
 *   --timeout N        Per-task timeout in seconds (default 600)
 *   --model provider/id  Model (default openai/gpt-5.2)
 *   --thinking level   Thinking level (default medium)
 */
import fs from "node:fs";
import path from "node:path";
import type { AssistantMessage } from "@mariozechner/pi-ai";
import { getModel } from "@mariozechner/pi-ai";
import type { ThinkingLevel } from "@mariozechner/pi-agent-core";
import {
	AuthStorage,
	type ResourceLoader,
	SessionManager,
	SettingsManager,
	createAgentSession,
	createCodingTools,
	createExtensionRuntime,
	createFindTool,
	createGrepTool,
	createLsTool,
	type ToolDefinition,
} from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

// --- Types ---

interface GaiaTask {
	task_id: string;
	question: string;
	expected_answer: string;
	file_name: string;
	level: number;
}

interface GaiaResult {
	task_id: string;
	expected_answer: string;
	model_answer: string | null;
	status: "success" | "error" | "no_answer";
	duration_ms: number;
	tokens: { input: number; output: number; total: number };
	cost: number;
	error?: string;
}

// --- Semaphore ---

class Semaphore {
	private queue: Array<() => void> = [];
	private active = 0;

	constructor(private max: number) {}

	async acquire(): Promise<void> {
		if (this.active < this.max) {
			this.active++;
			return;
		}
		return new Promise((resolve) => {
			this.queue.push(() => {
				this.active++;
				resolve();
			});
		});
	}

	release(): void {
		this.active--;
		const next = this.queue.shift();
		if (next) next();
	}
}

// --- Helpers ---

const BENCHMARK_DIR = path.resolve(import.meta.dirname ?? path.dirname(new URL(import.meta.url).pathname));
const DATA_DIR = path.join(BENCHMARK_DIR, "data");
const RESULTS_FILE = path.join(DATA_DIR, "results.jsonl");
const TASKS_FILE = path.join(DATA_DIR, "tasks.json");
const ATTACHMENTS_DIR = path.join(DATA_DIR, "attachments");
const WORKDIRS_DIR = path.join(DATA_DIR, "workdirs");

const PROMPT_TEMPLATE = `You are solving a GAIA benchmark task. Answer the question as precisely as possible.

Your final answer MUST be wrapped in <ANSWER>...</ANSWER> tags. The answer should be concise:
- A number (e.g., <ANSWER>42</ANSWER>)
- A few words (e.g., <ANSWER>Paris, France</ANSWER>)
- A comma-separated list (e.g., <ANSWER>apple, banana, cherry</ANSWER>)

Do NOT include units unless specifically asked. Do NOT include explanations inside ANSWER tags.
Use all available tools (web_search, bash, read, write, grep, find) to find the answer.

Question: {question}

After your research and reasoning, provide your final answer in <ANSWER>...</ANSWER> tags.`;

function extractAnswer(text: string): string | null {
	const match = text.match(/<ANSWER>([\s\S]*?)<\/ANSWER>/i);
	return match ? match[1].trim() : null;
}

function loadCompletedTaskIds(): Set<string> {
	const ids = new Set<string>();
	if (!fs.existsSync(RESULTS_FILE)) return ids;
	const lines = fs.readFileSync(RESULTS_FILE, "utf-8").trim().split("\n");
	for (const line of lines) {
		if (!line) continue;
		try {
			const r: GaiaResult = JSON.parse(line);
			ids.add(r.task_id);
		} catch {
			/* skip malformed lines */
		}
	}
	return ids;
}

function appendResult(result: GaiaResult): void {
	fs.appendFileSync(RESULTS_FILE, JSON.stringify(result) + "\n");
}

// --- Tavily Web Search Tool ---

function formatTavilyResults(data: { results?: Array<{ title: string; url: string; content: string }> }): string {
	if (!data.results || data.results.length === 0) return "No results found.";
	return data.results
		.map((r, i) => `[${i + 1}] ${r.title}\n    ${r.url}\n    ${r.content}`)
		.join("\n\n");
}

const tavilySearchTool: ToolDefinition = {
	name: "web_search",
	label: "Web Search",
	description: "Search the web using Tavily API. Returns relevant search results with titles, URLs, and content snippets.",
	parameters: Type.Object({
		query: Type.String({ description: "Search query" }),
		max_results: Type.Optional(Type.Number({ description: "Maximum number of results to return (default 5)" })),
	}),
	execute: async (_toolCallId, params) => {
		const apiKey = process.env.TAVILY_API_KEY;
		if (!apiKey) {
			return {
				content: [{ type: "text", text: "Error: TAVILY_API_KEY environment variable is not set." }],
				details: {},
			};
		}
		try {
			const resp = await fetch("https://api.tavily.com/search", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					api_key: apiKey,
					query: params.query,
					max_results: params.max_results ?? 5,
					include_raw_content: false,
				}),
			});
			if (!resp.ok) {
				return {
					content: [{ type: "text", text: `Tavily API error: ${resp.status} ${resp.statusText}` }],
					details: {},
				};
			}
			const data = await resp.json();
			return {
				content: [{ type: "text", text: formatTavilyResults(data) }],
				details: {},
			};
		} catch (err) {
			return {
				content: [{ type: "text", text: `Web search error: ${err instanceof Error ? err.message : String(err)}` }],
				details: {},
			};
		}
	},
};

// --- Resource Loader (minimal, no discovery) ---

function createMinimalResourceLoader(): ResourceLoader {
	return {
		getExtensions: () => ({ extensions: [], errors: [], runtime: createExtensionRuntime() }),
		getSkills: () => ({ skills: [], diagnostics: [] }),
		getPrompts: () => ({ prompts: [], diagnostics: [] }),
		getThemes: () => ({ themes: [], diagnostics: [] }),
		getAgentsFiles: () => ({ agentsFiles: [] }),
		getSystemPrompt: () => `You are a GAIA benchmark agent. Use all available tools to find accurate answers.
Always wrap your final answer in <ANSWER>...</ANSWER> tags.`,
		getAppendSystemPrompt: () => [],
		getPathMetadata: () => new Map(),
		extendResources: () => {},
		reload: async () => {},
	};
}

// --- CLI Argument Parsing ---

function parseArgs(): { concurrency: number; timeout: number; provider: string; modelId: string; thinking: ThinkingLevel } {
	const args = process.argv.slice(2);
	let concurrency = 3;
	let timeout = 600;
	let provider = "openai";
	let modelId = "gpt-5.2";
	let thinking: ThinkingLevel = "medium";

	for (let i = 0; i < args.length; i++) {
		if (args[i] === "--concurrency" && args[i + 1]) {
			concurrency = parseInt(args[i + 1], 10) || 3;
			i++;
		} else if (args[i] === "--timeout" && args[i + 1]) {
			timeout = parseInt(args[i + 1], 10) || 600;
			i++;
		} else if (args[i] === "--model" && args[i + 1]) {
			const parts = args[i + 1].split("/");
			if (parts.length === 2) {
				provider = parts[0];
				modelId = parts[1];
			}
			i++;
		} else if (args[i] === "--thinking" && args[i + 1]) {
			thinking = args[i + 1] as ThinkingLevel;
			i++;
		}
	}

	return { concurrency, timeout, provider, modelId, thinking };
}

// --- Run a Single Task ---

async function runTask(
	task: GaiaTask,
	config: { provider: string; modelId: string; thinking: ThinkingLevel; timeout: number },
): Promise<GaiaResult> {
	const taskWorkDir = path.join(WORKDIRS_DIR, task.task_id.slice(0, 8));
	fs.mkdirSync(taskWorkDir, { recursive: true });

	// Copy attachment if task has one
	if (task.file_name) {
		const src = path.join(ATTACHMENTS_DIR, task.file_name);
		if (fs.existsSync(src)) {
			fs.copyFileSync(src, path.join(taskWorkDir, task.file_name));
		}
	}

	const startTime = Date.now();
	let fullText = "";

	try {
		const model = getModel(config.provider as "openai", config.modelId as "gpt-5.2");
		if (!model) {
			throw new Error(`Model not found: ${config.provider}/${config.modelId}`);
		}

		const authStorage = AuthStorage.create();
		const settingsManager = SettingsManager.inMemory({
			compaction: { enabled: false },
			retry: { enabled: true, maxRetries: 3 },
		});

		const { session } = await createAgentSession({
			cwd: taskWorkDir,
			model,
			thinkingLevel: config.thinking,
			authStorage,
			resourceLoader: createMinimalResourceLoader(),
			tools: [
				...createCodingTools(taskWorkDir),
				createGrepTool(taskWorkDir),
				createFindTool(taskWorkDir),
				createLsTool(taskWorkDir),
			],
			customTools: [tavilySearchTool],
			sessionManager: SessionManager.inMemory(),
			settingsManager,
		});

		// Subscribe to capture text output
		session.subscribe((event) => {
			if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
				fullText += event.assistantMessageEvent.delta;
			}
		});

		const prompt = PROMPT_TEMPLATE.replace("{question}", task.question);

		// Run with timeout
		const timeoutMs = config.timeout * 1000;
		let timedOut = false;
		const timeoutId = setTimeout(async () => {
			timedOut = true;
			await session.abort();
		}, timeoutMs);

		try {
			await session.prompt(prompt);
		} finally {
			clearTimeout(timeoutId);
		}

		// Also extract from final messages in case streaming missed some
		const messages = session.state.messages;
		for (const msg of messages) {
			if (msg.role === "assistant") {
				const assistantMsg = msg as AssistantMessage;
				for (const c of assistantMsg.content) {
					if (c.type === "text" && !fullText.includes(c.text)) {
						fullText += c.text;
					}
				}
			}
		}

		// Collect token usage
		const stats = session.getSessionStats();

		const duration = Date.now() - startTime;
		const answer = extractAnswer(fullText);

		session.dispose();

		if (timedOut) {
			return {
				task_id: task.task_id,
				expected_answer: task.expected_answer,
				model_answer: answer,
				status: answer ? "success" : "error",
				duration_ms: duration,
				tokens: { input: stats.tokens.input, output: stats.tokens.output, total: stats.tokens.total },
				cost: stats.cost,
				error: answer ? undefined : "Timed out without answer",
			};
		}

		return {
			task_id: task.task_id,
			expected_answer: task.expected_answer,
			model_answer: answer,
			status: answer ? "success" : "no_answer",
			duration_ms: duration,
			tokens: { input: stats.tokens.input, output: stats.tokens.output, total: stats.tokens.total },
			cost: stats.cost,
		};
	} catch (err) {
		return {
			task_id: task.task_id,
			expected_answer: task.expected_answer,
			model_answer: null,
			status: "error",
			duration_ms: Date.now() - startTime,
			tokens: { input: 0, output: 0, total: 0 },
			cost: 0,
			error: err instanceof Error ? err.message : String(err),
		};
	} finally {
		// Clean up work directory
		fs.rmSync(taskWorkDir, { recursive: true, force: true });
	}
}

// --- Main ---

async function main() {
	const config = parseArgs();

	console.log(`GAIA Level 2 Benchmark Runner`);
	console.log(`Model: ${config.provider}/${config.modelId}, Thinking: ${config.thinking}`);
	console.log(`Concurrency: ${config.concurrency}, Timeout: ${config.timeout}s\n`);

	// Load tasks
	if (!fs.existsSync(TASKS_FILE)) {
		console.error("Tasks file not found at", TASKS_FILE);
		console.error("Copy from nanoclaw: cp ../nanoclaw/data/gaia/tasks.json benchmark/data/tasks.json");
		process.exit(1);
	}
	const tasks: GaiaTask[] = JSON.parse(fs.readFileSync(TASKS_FILE, "utf-8"));
	console.log(`Loaded ${tasks.length} tasks`);

	// Resume support
	const completed = loadCompletedTaskIds();
	const remaining = tasks.filter((t) => !completed.has(t.task_id));
	console.log(`Already completed: ${completed.size}, remaining: ${remaining.length}\n`);

	if (remaining.length === 0) {
		console.log("All tasks already completed.");
		return;
	}

	// Ensure output directory exists
	fs.mkdirSync(DATA_DIR, { recursive: true });
	fs.mkdirSync(WORKDIRS_DIR, { recursive: true });

	const semaphore = new Semaphore(config.concurrency);
	let done = completed.size;
	const total = tasks.length;

	const promises = remaining.map(async (task) => {
		await semaphore.acquire();
		const shortId = task.task_id.slice(0, 8);
		console.log(`[${done + 1}/${total}] Starting ${shortId}...`);

		try {
			const result = await runTask(task, config);
			appendResult(result);
			done++;

			const tag = result.status === "success" ? "OK" : result.status === "error" ? "ERR" : "NA";
			console.log(
				`[${done}/${total}] ${tag} ${shortId} ` +
					`(${Math.round(result.duration_ms / 1000)}s) ` +
					`answer=${result.model_answer ?? "NONE"} ` +
					`tokens=${result.tokens.total} cost=$${result.cost.toFixed(4)}`,
			);
		} catch (err) {
			done++;
			console.error(`[${done}/${total}] FATAL ${shortId}:`, err);
		} finally {
			semaphore.release();
		}
	});

	await Promise.all(promises);
	console.log(`\nDone. Results: ${RESULTS_FILE}`);
	console.log("Run 'npx tsx benchmark/score.ts' to see accuracy.");
}

main().catch((err) => {
	console.error("Benchmark failed:", err);
	process.exit(1);
});
