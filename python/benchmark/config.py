"""Benchmark configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Paths
BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BENCHMARK_DIR), "..", "benchmark", "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")
WORKDIRS_DIR = os.path.join(DATA_DIR, "workdirs")
RESULTS_FILE = os.path.join(DATA_DIR, "results.jsonl")
TRAJECTORIES_DIR = os.path.join(DATA_DIR, "trajectories")


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    model_provider: str = "openai"
    model_id: str = "gpt-5.2"
    reasoning: str | None = "high"
    concurrency: int = 3
    timeout: int = 600  # seconds per task
    level: int = 2
    max_tasks: int | None = None  # None = all tasks
    results_file: str = RESULTS_FILE
    trajectories_dir: str = TRAJECTORIES_DIR
    save_trajectories: bool = True
