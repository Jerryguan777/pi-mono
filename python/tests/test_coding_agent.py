"""Tests for pi_coding_agent — system prompt, model registry, auth, settings."""

import json
import os
import tempfile

import pytest

from pi_ai.types import Model, ModelCost
from pi_agent.types import AgentTool, AgentToolResult
from pi_ai.types import TextContent

from pi_coding_agent.auth_storage import AuthStorage
from pi_coding_agent.model_registry import ModelRegistry
from pi_coding_agent.resource_loader import ContextFile, load_project_context_files
from pi_coding_agent.settings_manager import Settings, SettingsManager
from pi_coding_agent.system_prompt import build_system_prompt


# --- System prompt tests ---


class MockTool(AgentTool):
    def __init__(self, name: str = "test_tool", description: str = "A test tool"):
        self.name = name
        self.label = name
        self.description = description
        self.parameters = {"type": "object", "properties": {}}

    async def execute(self, tool_call_id, params, on_update=None, abort_signal=None):
        return AgentToolResult(content=[TextContent(text="ok")])


def test_build_system_prompt_default():
    """Default prompt includes base instructions and tools."""
    tools = [MockTool(name="read", description="Read a file")]
    prompt = build_system_prompt(tools=tools, cwd="/tmp/test")

    assert "helpful AI coding assistant" in prompt
    assert "read" in prompt.lower()
    assert "Read a file" in prompt
    assert "/tmp/test" in prompt


def test_build_system_prompt_custom():
    """Custom prompt overrides base instructions."""
    prompt = build_system_prompt(custom_prompt="You are a math tutor.", cwd="/tmp")
    assert "math tutor" in prompt
    assert "helpful AI coding assistant" not in prompt


def test_build_system_prompt_with_context():
    """Context files are included in the prompt."""
    context_files = [
        ContextFile(path="/project/AGENTS.md", content="# Project Rules\n- Always use type hints"),
    ]
    prompt = build_system_prompt(context_files=context_files, cwd="/tmp")

    assert "Project Context" in prompt
    assert "Always use type hints" in prompt
    assert "AGENTS.md" in prompt


def test_build_system_prompt_with_append():
    """Appended system prompt appears at the end."""
    prompt = build_system_prompt(
        append_system_prompt="Remember: always use Python 3.11+",
        cwd="/tmp",
    )
    assert "always use Python 3.11+" in prompt


def test_build_system_prompt_includes_datetime():
    """Prompt includes current date and working directory."""
    prompt = build_system_prompt(cwd="/home/user/project")
    assert "Current date:" in prompt
    assert "/home/user/project" in prompt


# --- Resource loader tests ---


def test_resource_loader_agents_md():
    """Discovers AGENTS.md files in directory hierarchy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create AGENTS.md in a parent directory
        parent_dir = os.path.join(tmpdir, "parent")
        child_dir = os.path.join(parent_dir, "child")
        os.makedirs(child_dir)

        agents_path = os.path.join(parent_dir, "AGENTS.md")
        with open(agents_path, "w") as f:
            f.write("# Project Rules\nRule 1: Be nice")

        files = load_project_context_files(cwd=child_dir)

        # Should find the AGENTS.md in parent
        paths = [cf.path for cf in files]
        assert agents_path in paths

        # Should have correct content
        matching = [cf for cf in files if cf.path == agents_path]
        assert len(matching) == 1
        assert "Be nice" in matching[0].content


def test_resource_loader_claude_md():
    """Discovers CLAUDE.md files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        claude_path = os.path.join(tmpdir, "CLAUDE.md")
        with open(claude_path, "w") as f:
            f.write("# Claude Instructions")

        files = load_project_context_files(cwd=tmpdir)
        paths = [cf.path for cf in files]
        assert claude_path in paths


def test_resource_loader_no_files():
    """Returns empty list when no context files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        files = load_project_context_files(cwd=tmpdir)
        # May find files from home dir, but tmpdir itself has none
        tmpdir_files = [cf for cf in files if cf.path.startswith(tmpdir)]
        assert len(tmpdir_files) == 0


# --- Model registry tests ---


@pytest.mark.asyncio
async def test_model_registry_built_in():
    """Returns all built-in models."""
    auth = AuthStorage.in_memory()
    registry = ModelRegistry(auth)
    all_models = registry.get_all()

    assert len(all_models) > 0
    # Should have models from all 3 providers
    providers = {m.provider for m in all_models}
    assert "openai" in providers
    assert "anthropic" in providers
    assert "google" in providers


def test_model_registry_find():
    """Find by provider + model_id."""
    auth = AuthStorage.in_memory()
    registry = ModelRegistry(auth)

    model = registry.find("anthropic", "claude-opus-4-6-20250723")
    assert model is not None
    assert model.name == "Claude Opus 4.6"

    missing = registry.find("nonexistent", "nope")
    assert missing is None


@pytest.mark.asyncio
async def test_model_registry_custom_models():
    """Custom models from JSON file are included."""
    with tempfile.TemporaryDirectory() as tmpdir:
        models_path = os.path.join(tmpdir, "models.json")
        with open(models_path, "w") as f:
            json.dump({
                "custom_provider": {
                    "custom-model-1": {
                        "name": "Custom Model 1",
                        "api": "openai-responses",
                        "base_url": "https://custom.api.com/v1",
                        "reasoning": True,
                        "context_window": 64000,
                        "max_tokens": 8192,
                        "cost": {"input": 1.0, "output": 2.0},
                    }
                }
            }, f)

        auth = AuthStorage.in_memory()
        registry = ModelRegistry(auth, models_json_path=models_path)

        model = registry.find("custom_provider", "custom-model-1")
        assert model is not None
        assert model.name == "Custom Model 1"
        assert model.context_window == 64000


@pytest.mark.asyncio
async def test_model_registry_available_with_key(monkeypatch):
    """get_available only returns models with API keys."""
    # Clear env vars so only in-memory keys are used
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    auth = AuthStorage.in_memory({"openai": "sk-test-key"})
    registry = ModelRegistry(auth)

    available = await registry.get_available()
    providers = {m.provider for m in available}
    assert "openai" in providers
    # anthropic and google should not be available (no keys)
    assert "anthropic" not in providers
    assert "google" not in providers


# --- Auth storage tests ---


@pytest.mark.asyncio
async def test_auth_storage_env_fallback(monkeypatch):
    """API key falls back to environment variable."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

    auth = AuthStorage.in_memory()
    key = await auth.get_api_key("openai")
    assert key == "sk-from-env"


@pytest.mark.asyncio
async def test_auth_storage_file():
    """API key from auth.json file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        auth_path = os.path.join(tmpdir, "auth.json")
        with open(auth_path, "w") as f:
            json.dump({"anthropic": "sk-from-file"}, f)

        auth = AuthStorage(auth_path=auth_path)
        key = await auth.get_api_key("anthropic")
        assert key == "sk-from-file"


@pytest.mark.asyncio
async def test_auth_storage_runtime_override():
    """Runtime override takes precedence."""
    auth = AuthStorage.in_memory({"openai": "sk-from-data"})
    auth.set_runtime_override("openai", "sk-override")

    key = await auth.get_api_key("openai")
    assert key == "sk-override"


@pytest.mark.asyncio
async def test_auth_storage_set_and_persist():
    """set_api_key persists to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        auth_path = os.path.join(tmpdir, "auth.json")
        auth = AuthStorage(auth_path=auth_path)

        auth.set_api_key("google", "sk-google-key")

        # Verify persisted
        with open(auth_path) as f:
            data = json.load(f)
        assert data["google"] == "sk-google-key"


@pytest.mark.asyncio
async def test_auth_storage_no_key():
    """Returns None when no key available."""
    auth = AuthStorage.in_memory()
    key = await auth.get_api_key("nonexistent_provider")
    assert key is None


# --- Settings manager tests ---


def test_settings_manager_defaults():
    """Default settings have sensible values."""
    mgr = SettingsManager.in_memory()
    assert mgr.get_default_provider() is None
    assert mgr.get_steering_mode() == "one-at-a-time"
    assert mgr.get_compaction_settings().enabled is True
    assert mgr.get_retry_settings().max_retries == 3


def test_settings_manager_merge():
    """Global + project settings merge correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create global settings
        global_dir = os.path.join(tmpdir, "global")
        os.makedirs(global_dir, exist_ok=True)
        global_path = os.path.join(global_dir, "settings.json")
        with open(global_path, "w") as f:
            json.dump({
                "default_provider": "openai",
                "default_model": "gpt-4o",
                "steering_mode": "all",
                "compaction": {"reserve_tokens": 8192},
            }, f)

        # Create project settings (overrides some global)
        project_dir = os.path.join(tmpdir, "project")
        os.makedirs(project_dir, exist_ok=True)
        project_path = os.path.join(project_dir, "settings.json")
        with open(project_path, "w") as f:
            json.dump({
                "default_model": "gpt-5",
                "retry": {"max_retries": 5},
            }, f)

        settings = Settings()
        from pi_coding_agent.settings_manager import _merge_from_file
        _merge_from_file(settings, global_path)
        _merge_from_file(settings, project_path)

        # Global setting kept
        assert settings.default_provider == "openai"
        assert settings.steering_mode == "all"
        assert settings.compaction.reserve_tokens == 8192

        # Project overrides
        assert settings.default_model == "gpt-5"
        assert settings.retry.max_retries == 5


def test_settings_manager_save():
    """Save settings to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "settings.json")
        mgr = SettingsManager(
            Settings(default_provider="anthropic"),
            global_path=path,
        )
        mgr.save_global()

        with open(path) as f:
            data = json.load(f)
        assert data["default_provider"] == "anthropic"


def test_settings_manager_setters():
    """Setting setters work."""
    mgr = SettingsManager.in_memory()
    mgr.set_default_provider("google")
    mgr.set_default_model("gemini-3-pro")
    mgr.set_default_thinking_level("high")

    assert mgr.get_default_provider() == "google"
    assert mgr.get_default_model() == "gemini-3-pro"
    assert mgr.get_default_thinking_level() == "high"
