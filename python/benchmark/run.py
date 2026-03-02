"""GAIA benchmark runner — run tasks concurrently with agent + tools."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pi_ai.api_registry import register_default_providers
from pi_ai.models import get_model
from pi_ai.types import StreamOptions, TextContent, ThinkingContent, ToolCall, UserMessage
from pi_agent.agent_loop import agent_loop
from pi_agent.types import (
    AgentEndEvent,
    AgentTool,
    MessageEndEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from pi_ai.types import AssistantMessage, ToolResultMessage
from pi_tools.bash_tool import BashTool
from pi_tools.read_tool import ReadTool
from pi_tools.write_tool import WriteTool
from pi_tools.edit_tool import EditTool
from pi_tools.grep_tool import GrepTool
from pi_tools.find_tool import FindTool
from pi_tools.ls_tool import LsTool
from pi_tools.web_search import WebSearchTool

from benchmark.config import (
    ATTACHMENTS_DIR,
    BenchmarkConfig,
    DATA_DIR,
    TASKS_FILE,
    TRAJECTORIES_DIR,
    WORKDIRS_DIR,
)


SYSTEM_PROMPT = """You are a helpful assistant that answers questions accurately and concisely.

You have access to tools for file operations, web search, and bash commands.
Use them as needed to find the answer.

IMPORTANT: When you have found the answer, respond with ONLY the answer.
Do not include explanations, reasoning, or extra text.
The answer should be the exact value requested — a number, name, word, or short phrase.
Do not prefix with "The answer is" or similar.
"""


def _serialize_content_block(block: TextContent | ThinkingContent | ToolCall) -> dict:
    """Serialize a content block to a JSON-safe dict."""
    if isinstance(block, TextContent):
        return {"type": "text", "text": block.text}
    if isinstance(block, ThinkingContent):
        return {"type": "thinking", "thinking": block.thinking}
    if isinstance(block, ToolCall):
        return {"type": "toolCall", "id": block.id, "name": block.name, "arguments": block.arguments}
    return {"type": "unknown"}


def _serialize_message(msg: Any) -> dict:
    """Serialize a Message to a JSON-safe dict."""
    if isinstance(msg, AssistantMessage):
        return {
            "role": "assistant",
            "content": [_serialize_content_block(b) for b in msg.content],
            "model": msg.model,
            "stop_reason": msg.stop_reason,
            "usage": {
                "input": msg.usage.input,
                "output": msg.usage.output,
                "cache_read": msg.usage.cache_read,
                "cache_write": msg.usage.cache_write,
                "total_tokens": msg.usage.total_tokens,
                "cost": msg.usage.cost.total,
            },
            "timestamp": msg.timestamp,
        }
    if isinstance(msg, ToolResultMessage):
        text_parts = [c.text for c in msg.content if isinstance(c, TextContent)]
        return {
            "role": "toolResult",
            "tool_call_id": msg.tool_call_id,
            "tool_name": msg.tool_name,
            "content": "\n".join(text_parts),
            "is_error": msg.is_error,
            "timestamp": msg.timestamp,
        }
    if isinstance(msg, UserMessage):
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        return {"role": "user", "content": content, "timestamp": msg.timestamp}
    return {"role": "unknown"}


class TrajectoryWriter:
    """Append trajectory events to a JSONL file for a single task."""

    def __init__(self, path: str) -> None:
        self._path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Truncate
        with open(path, "w"):
            pass

    def write(self, entry: dict) -> None:
        with open(self._path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_tasks(config: BenchmarkConfig) -> list[dict]:
    """Load GAIA tasks from tasks.json."""
    with open(TASKS_FILE, "r") as f:
        tasks = json.load(f)

    # Filter by level
    tasks = [t for t in tasks if t.get("level") == config.level]

    if config.max_tasks:
        tasks = tasks[:config.max_tasks]

    return tasks


def create_tools(workdir: str) -> list[AgentTool]:
    """Create the tool set for a benchmark task."""
    return [
        BashTool(workdir),
        ReadTool(workdir),
        WriteTool(workdir),
        EditTool(workdir),
        GrepTool(workdir),
        FindTool(workdir),
        LsTool(workdir),
        WebSearchTool(),
    ]


def setup_workdir(task: dict) -> str:
    """Create a working directory for a task, copy attachments."""
    task_id = task["task_id"]
    workdir = os.path.join(WORKDIRS_DIR, task_id)
    os.makedirs(workdir, exist_ok=True)

    # Copy attachment if any
    file_name = task.get("file_name", "")
    if file_name:
        src = os.path.join(ATTACHMENTS_DIR, file_name)
        dst = os.path.join(workdir, file_name)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)

    return workdir


def extract_answer(messages: list) -> str:
    """Extract the final answer from agent messages."""
    # Look for the last assistant message with text content
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage):
            text_parts = []
            for block in msg.content:
                if isinstance(block, TextContent):
                    text_parts.append(block.text)
            if text_parts:
                answer = "\n".join(text_parts).strip()
                # Clean up common prefixes
                for prefix in ["The answer is ", "Answer: ", "ANSWER: ", "Final answer: "]:
                    if answer.lower().startswith(prefix.lower()):
                        answer = answer[len(prefix):]
                return answer.strip()
    return ""


async def run_task(
    task: dict,
    config: BenchmarkConfig,
    semaphore: asyncio.Semaphore,
    results_lock: asyncio.Lock | None = None,
    results_file: str | None = None,
) -> dict:
    """Run a single GAIA task and return the result."""
    task_id = task["task_id"]
    question = task["question"]
    expected = task.get("expected_answer", "")

    async with semaphore:
        start_time = time.time()
        model_answer = ""
        status = "error"
        tokens = {"input": 0, "output": 0, "total": 0}
        cost = 0.0
        traj: TrajectoryWriter | None = None

        try:
            workdir = setup_workdir(task)
            model = get_model(config.model_provider, config.model_id)
            tools = create_tools(workdir)
            options = StreamOptions(reasoning=config.reasoning)

            # Replace attachment path placeholder
            q = question
            if task.get("file_name"):
                attachment_path = os.path.join(workdir, task["file_name"])
                q = q.replace(
                    f"[Attached file for this task: /workspace/group/attachments/{task['file_name']}]",
                    f"[Attached file: {attachment_path}]",
                )

            user_msg = UserMessage(
                content=q,
                timestamp=int(time.time() * 1000),
            )

            # Trajectory writer
            if config.save_trajectories:
                traj_path = os.path.join(config.trajectories_dir, f"{task_id}.jsonl")
                traj = TrajectoryWriter(traj_path)
                traj.write({"type": "task_start", "task_id": task_id, "question": q, "expected_answer": expected, "timestamp": int(time.time() * 1000)})

            # Collect messages from agent loop
            all_messages = []
            turn_num = 0

            async def run_agent():
                nonlocal all_messages, turn_num
                async for event in agent_loop(
                    prompts=[user_msg],
                    system_prompt=SYSTEM_PROMPT,
                    messages=[],
                    tools=tools,
                    model=model,
                    options=options,
                ):
                    if isinstance(event, TurnStartEvent):
                        turn_num += 1
                        if traj:
                            traj.write({"type": "turn_start", "turn": turn_num, "timestamp": int(time.time() * 1000)})

                    elif isinstance(event, MessageEndEvent):
                        all_messages.append(event.message)
                        if traj:
                            traj.write({"type": "message_end", **_serialize_message(event.message)})

                    elif isinstance(event, ToolExecutionStartEvent):
                        if traj:
                            traj.write({"type": "tool_execution_start", "tool_name": event.tool_name, "tool_call_id": event.tool_call_id, "args": event.args, "timestamp": int(time.time() * 1000)})

                    elif isinstance(event, ToolExecutionEndEvent):
                        if traj:
                            result_text = ""
                            if event.result and event.result.content:
                                text_parts = [c.text for c in event.result.content if isinstance(c, TextContent)]
                                result_text = "\n".join(text_parts)
                            traj.write({"type": "tool_execution_end", "tool_name": event.tool_name, "tool_call_id": event.tool_call_id, "is_error": event.is_error, "result": result_text, "timestamp": int(time.time() * 1000)})

                    elif isinstance(event, TurnEndEvent):
                        if traj:
                            sr = event.message.stop_reason if isinstance(event.message, AssistantMessage) else "n/a"
                            traj.write({"type": "turn_end", "turn": turn_num, "stop_reason": sr, "tool_results_count": len(event.tool_results), "timestamp": int(time.time() * 1000)})

                    elif isinstance(event, AgentEndEvent):
                        if traj:
                            traj.write({"type": "agent_end", "total_messages": len(event.messages), "turns": turn_num, "timestamp": int(time.time() * 1000)})

            await asyncio.wait_for(run_agent(), timeout=config.timeout)

            model_answer = extract_answer(all_messages)

            # Aggregate token usage
            for msg in all_messages:
                if isinstance(msg, AssistantMessage):
                    tokens["input"] += msg.usage.input
                    tokens["output"] += msg.usage.output
                    tokens["total"] += msg.usage.total_tokens
                    cost += msg.usage.cost.total

            status = "success"

        except asyncio.TimeoutError:
            status = "timeout"
            model_answer = ""
            if traj:
                traj.write({"type": "task_error", "error": "timeout", "timestamp": int(time.time() * 1000)})
        except Exception as e:
            status = "error"
            model_answer = str(e)
            if traj:
                traj.write({"type": "task_error", "error": str(e), "timestamp": int(time.time() * 1000)})

        duration_ms = int((time.time() - start_time) * 1000)

        result = {
            "task_id": task_id,
            "expected_answer": expected,
            "model_answer": model_answer,
            "status": status,
            "duration_ms": duration_ms,
            "tokens": tokens,
            "cost": cost,
        }

        # Write trajectory summary
        if traj:
            traj.write({"type": "task_end", **result})

        # Write result incrementally
        if results_lock and results_file:
            async with results_lock:
                with open(results_file, "a") as f:
                    f.write(json.dumps(result) + "\n")

        # Print progress (use answers_match for accurate match icon)
        from benchmark.score import answers_match
        is_match = status == "success" and answers_match(expected, model_answer)
        match_icon = "\u2713" if is_match else "\u2717"
        print(f"  {match_icon} {task_id[:8]}... [{status}] {duration_ms/1000:.1f}s | expected: {expected[:30]} | got: {model_answer[:30]}", flush=True)

        return result


async def run_benchmark(config: BenchmarkConfig) -> None:
    """Run the full GAIA benchmark."""
    register_default_providers()

    tasks = load_tasks(config)
    print(f"\nGAIA Benchmark — Level {config.level}", flush=True)
    print(f"Model: {config.model_provider}/{config.model_id}", flush=True)
    print(f"Tasks: {len(tasks)} | Concurrency: {config.concurrency} | Timeout: {config.timeout}s", flush=True)
    print(f"Results: {config.results_file}", flush=True)
    if config.save_trajectories:
        print(f"Trajectories: {config.trajectories_dir}", flush=True)
    print(f"{'='*60}\n", flush=True)

    semaphore = asyncio.Semaphore(config.concurrency)
    results_lock = asyncio.Lock()

    # Create results directory
    os.makedirs(os.path.dirname(config.results_file), exist_ok=True)
    os.makedirs(WORKDIRS_DIR, exist_ok=True)
    if config.save_trajectories:
        os.makedirs(config.trajectories_dir, exist_ok=True)

    # Clear results file
    with open(config.results_file, "w") as f:
        pass

    # Run tasks concurrently (results written incrementally in run_task)
    coros = [run_task(task, config, semaphore, results_lock, config.results_file) for task in tasks]
    results = await asyncio.gather(*coros, return_exceptions=True)

    # Write any exception results that weren't written by run_task
    async with results_lock:
        with open(config.results_file, "a") as f:
            for result in results:
                if isinstance(result, Exception):
                    f.write(json.dumps({"status": "error", "error": str(result)}) + "\n")

    # Print summary
    from benchmark.score import score_results
    scores = score_results(config.results_file)
    print(f"\n{'='*60}")
    print(f"Results: {scores['correct']}/{scores['total']} correct ({scores['accuracy']:.1%})")
    print(f"Errors: {scores['errors']} | Timeouts: {scores['timeouts']}")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GAIA benchmark")
    parser.add_argument("--provider", default="openai", help="Model provider")
    parser.add_argument("--model", default="gpt-5.2", help="Model ID")
    parser.add_argument("--reasoning", default="high", help="Reasoning level")
    parser.add_argument("--concurrency", type=int, default=3, help="Max concurrent tasks")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout per task (seconds)")
    parser.add_argument("--level", type=int, default=2, help="GAIA level (1, 2, or 3)")
    parser.add_argument("--max-tasks", type=int, default=None, help="Max tasks to run")
    parser.add_argument("--results", default=None, help="Results file path")
    parser.add_argument("--no-trajectories", action="store_true", help="Disable trajectory recording")
    parser.add_argument("--trajectories-dir", default=None, help="Trajectories directory path")
    args = parser.parse_args()

    config = BenchmarkConfig(
        model_provider=args.provider,
        model_id=args.model,
        reasoning=args.reasoning if args.reasoning != "none" else None,
        concurrency=args.concurrency,
        timeout=args.timeout,
        level=args.level,
        max_tasks=args.max_tasks,
        results_file=args.results or BenchmarkConfig.results_file,
        save_trajectories=not args.no_trajectories,
        trajectories_dir=args.trajectories_dir or BenchmarkConfig.trajectories_dir,
    )

    asyncio.run(run_benchmark(config))


if __name__ == "__main__":
    main()
