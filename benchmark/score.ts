/**
 * Score GAIA benchmark results.
 *
 * Reads results.jsonl, normalizes answers, computes accuracy.
 *
 * Usage: npx tsx benchmark/score.ts
 */
import fs from "node:fs";
import path from "node:path";

interface GaiaResult {
	task_id: string;
	expected_answer: string;
	model_answer: string | null;
	status: "success" | "error" | "no_answer";
	duration_ms: number;
	tokens?: { input: number; output: number; total: number };
	cost?: number;
	error?: string;
}

const BENCHMARK_DIR = path.resolve(import.meta.dirname ?? path.dirname(new URL(import.meta.url).pathname));
const RESULTS_FILE = path.join(BENCHMARK_DIR, "data", "results.jsonl");

function normalize(s: string): string {
	return s
		.toLowerCase()
		.trim()
		.replace(/\.$/, "") // trailing period
		.replace(/^["']|["']$/g, "") // surrounding quotes
		.replace(/^\$/, "") // leading $
		.replace(/,(\d{3})/g, "$1") // number commas: 1,000 -> 1000
		.trim();
}

function fuzzyMatch(expected: string, actual: string): boolean {
	const ne = normalize(expected);
	const na = normalize(actual);

	// Exact match
	if (ne === na) return true;

	// Numeric fuzzy match
	const numE = parseFloat(ne);
	const numA = parseFloat(na);
	if (!isNaN(numE) && !isNaN(numA)) {
		if (Math.abs(numE - numA) < 1e-6) return true;
		// Relative tolerance for larger numbers
		if (numE !== 0 && Math.abs((numE - numA) / numE) < 1e-6) return true;
	}

	return false;
}

function main() {
	if (!fs.existsSync(RESULTS_FILE)) {
		console.error("Results file not found at", RESULTS_FILE);
		console.error("Run 'npx tsx benchmark/run.ts' first.");
		process.exit(1);
	}

	const lines = fs.readFileSync(RESULTS_FILE, "utf-8").trim().split("\n");
	const results: GaiaResult[] = [];
	for (const line of lines) {
		if (!line) continue;
		try {
			results.push(JSON.parse(line));
		} catch {
			/* skip */
		}
	}

	let correct = 0;
	let answered = 0;
	let errors = 0;
	const wrong: Array<{ id: string; expected: string; got: string | null }> = [];
	let totalDuration = 0;
	let totalTokens = 0;
	let totalCost = 0;

	for (const r of results) {
		totalDuration += r.duration_ms;
		totalTokens += r.tokens?.total ?? 0;
		totalCost += r.cost ?? 0;

		if (r.status === "error") {
			errors++;
			wrong.push({ id: r.task_id.slice(0, 8), expected: r.expected_answer, got: r.error ?? "ERROR" });
			continue;
		}

		if (!r.model_answer) {
			wrong.push({ id: r.task_id.slice(0, 8), expected: r.expected_answer, got: null });
			continue;
		}

		answered++;
		if (fuzzyMatch(r.expected_answer, r.model_answer)) {
			correct++;
		} else {
			wrong.push({ id: r.task_id.slice(0, 8), expected: r.expected_answer, got: r.model_answer });
		}
	}

	const total = results.length;
	const accuracy = total > 0 ? ((correct / total) * 100).toFixed(1) : "0.0";
	const avgDuration = total > 0 ? Math.round(totalDuration / total / 1000) : 0;
	const avgTokens = total > 0 ? Math.round(totalTokens / total) : 0;

	console.log("=== GAIA Level 2 Benchmark Results ===\n");
	console.log(`Total tasks:    ${total}`);
	console.log(`Answered:       ${answered}`);
	console.log(`Errors:         ${errors}`);
	console.log(`No answer:      ${total - answered - errors}`);
	console.log(`Correct:        ${correct}`);
	console.log(`Accuracy:       ${accuracy}%`);
	console.log(`Avg duration:   ${avgDuration}s`);
	console.log(`Avg tokens:     ${avgTokens}`);
	console.log(`Total cost:     $${totalCost.toFixed(2)}`);

	if (wrong.length > 0) {
		console.log(`\n=== Wrong/Missing Answers (${wrong.length}) ===\n`);
		for (const w of wrong) {
			console.log(`  ${w.id}  expected: ${w.expected}  got: ${w.got ?? "NO ANSWER"}`);
		}
	}
}

main();
