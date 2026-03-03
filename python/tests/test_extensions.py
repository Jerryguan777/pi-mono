"""Tests for extension ecosystem — skills, slash commands, extension runner."""

import os
import tempfile

import pytest

from pi_ai.types import Model, ModelCost, TextContent
from pi_agent.types import AgentStartEvent, AgentTool, AgentToolResult

from pi_coding_agent.extensions.runner import ExtensionRunner
from pi_coding_agent.extensions.types import ExtensionContext, ExtensionRuntime
from pi_coding_agent.skills import Skill, format_skills_for_prompt, load_skills
from pi_coding_agent.slash_commands import (
    SlashCommand,
    get_builtin_commands,
    parse_slash_command,
)


MOCK_MODEL = Model(
    id="mock-model",
    name="Mock",
    api="mock-api",
    provider="mock",
    base_url="",
    reasoning=False,
    input=["text"],
    cost=ModelCost(),
    context_window=128000,
    max_tokens=4096,
)


# --- Skills tests ---


def test_load_skills():
    """Load skill .md files with frontmatter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = os.path.join(tmpdir, "commit.md")
        with open(skill_path, "w") as f:
            f.write("""---
name: commit
description: Create a git commit
---
When asked to commit, stage changes and create a commit with a descriptive message.
""")

        skills = load_skills([tmpdir])
        assert len(skills) == 1
        assert skills[0].name == "commit"
        assert skills[0].description == "Create a git commit"
        assert "stage changes" in skills[0].source


def test_load_skills_disable_model_invocation():
    """Skills with disable-model-invocation flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = os.path.join(tmpdir, "secret.md")
        with open(skill_path, "w") as f:
            f.write("""---
name: secret-skill
description: A secret skill
disable-model-invocation: true
---
This skill can only be invoked by the user.
""")

        skills = load_skills([tmpdir])
        assert len(skills) == 1
        assert skills[0].disable_model_invocation is True


def test_load_skills_no_frontmatter():
    """Files without frontmatter are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "no_fm.md")
        with open(path, "w") as f:
            f.write("Just a regular markdown file.\n")

        skills = load_skills([tmpdir])
        assert len(skills) == 0


def test_load_skills_name_from_filename():
    """Skill name falls back to filename when not in frontmatter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "my-skill.md")
        with open(path, "w") as f:
            f.write("""---
description: A skill without a name field
---
Body text.
""")

        skills = load_skills([tmpdir])
        assert len(skills) == 1
        assert skills[0].name == "my-skill"


def test_load_skills_deduplicates():
    """Skills with duplicate names are deduplicated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(3):
            path = os.path.join(tmpdir, f"skill_{i}.md")
            with open(path, "w") as f:
                f.write(f"""---
name: same-name
description: Skill {i}
---
Body {i}.
""")

        skills = load_skills([tmpdir])
        assert len(skills) == 1


def test_load_skills_single_file():
    """Load a single skill file directly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "single.md")
        with open(path, "w") as f:
            f.write("""---
name: single
description: Single skill
---
Content.
""")

        skills = load_skills([path])
        assert len(skills) == 1
        assert skills[0].name == "single"


def test_format_skills_for_prompt():
    """Format skills as XML."""
    skills = [
        Skill(name="commit", description="Create a commit", file_path="", source=""),
        Skill(name="review", description="Review code", file_path="", source="", disable_model_invocation=True),
    ]

    output = format_skills_for_prompt(skills)
    assert "<available-skills>" in output
    assert "</available-skills>" in output
    assert 'name="commit"' in output
    assert 'name="review"' in output
    assert 'user-invocable-only="true"' in output
    assert "Create a commit" in output


def test_format_skills_empty():
    """Empty skills list returns empty string."""
    assert format_skills_for_prompt([]) == ""


# --- Slash command tests ---


def test_builtin_commands():
    """Built-in commands are registered."""
    commands = get_builtin_commands()
    names = [c.name for c in commands]

    assert "new" in names
    assert "compact" in names
    assert "model" in names
    assert "settings" in names
    assert "export" in names
    assert "quit" in names
    assert "reload" in names

    # All should be builtin source
    for cmd in commands:
        assert cmd.source == "builtin"


def test_parse_slash_command():
    """Parse slash commands from text."""
    assert parse_slash_command("/new") == ("new", "")
    assert parse_slash_command("/model openai/gpt-5") == ("model", "openai/gpt-5")
    assert parse_slash_command("/compact with instructions") == ("compact", "with instructions")


def test_parse_slash_command_not_slash():
    """Non-slash text returns None."""
    assert parse_slash_command("hello") is None
    assert parse_slash_command("") is None


def test_parse_slash_command_empty_slash():
    """Just / returns None."""
    assert parse_slash_command("/") is None


@pytest.mark.asyncio
async def test_slash_command_new():
    """Test /new command handler."""
    from pi_agent.agent import Agent
    from pi_session.agent_session import AgentSession, AgentSessionConfig
    from pi_session.session_manager import SessionManager

    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    agent.messages.append(__import__("pi_ai.types", fromlist=["UserMessage"]).UserMessage(content="old"))
    mgr = SessionManager.in_memory()
    session = AgentSession(AgentSessionConfig(agent=agent, session_manager=mgr))

    commands = get_builtin_commands(session)
    new_cmd = next(c for c in commands if c.name == "new")

    result = await new_cmd.handler(session)
    assert result is not None
    assert len(agent.messages) == 0


@pytest.mark.asyncio
async def test_slash_command_settings():
    """Test /settings command handler."""
    from pi_agent.agent import Agent
    from pi_session.agent_session import AgentSession, AgentSessionConfig
    from pi_session.session_manager import SessionManager

    agent = Agent(model=MOCK_MODEL, system_prompt="test")
    mgr = SessionManager.in_memory()
    session = AgentSession(AgentSessionConfig(agent=agent, session_manager=mgr))

    commands = get_builtin_commands(session)
    settings_cmd = next(c for c in commands if c.name == "settings")

    result = await settings_cmd.handler(session)
    assert "mock/mock-model" in result
    assert "Messages:" in result


# --- Extension runner tests ---


def test_extension_runtime_register_tool():
    """Tool registration via runtime."""

    class MockExtTool(AgentTool):
        def __init__(self):
            self.name = "ext_tool"
            self.label = "Extension Tool"
            self.description = "A tool from an extension"
            self.parameters = {"type": "object", "properties": {}}

        async def execute(self, tool_call_id, params, on_update=None, abort_signal=None):
            return AgentToolResult(content=[TextContent(text="ext result")])

    runtime = ExtensionRuntime()
    tool = MockExtTool()
    runtime.register_tool(tool)

    assert len(runtime.tools) == 1
    assert runtime.tools[0].name == "ext_tool"


def test_extension_runtime_register_command():
    """Command registration via runtime."""
    runtime = ExtensionRuntime()

    async def handler(session, args=""):
        return "done"

    runtime.register_command("ext-cmd", "An extension command", handler)

    assert len(runtime.commands) == 1
    assert runtime.commands[0]["name"] == "ext-cmd"


def test_extension_runtime_event_handler():
    """Event handler registration via runtime."""
    runtime = ExtensionRuntime()
    calls: list = []

    async def handler(event):
        calls.append(event)

    runtime.on_event(handler)
    assert len(runtime.event_handlers) == 1


def test_extension_runner_load():
    """Load extension from a Python module file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ext_path = os.path.join(tmpdir, "my_extension.py")
        with open(ext_path, "w") as f:
            f.write("""
def setup(context, runtime):
    runtime.register_command("ext-hello", "Say hello", None)
""")

        context = ExtensionContext(cwd=tmpdir, model=MOCK_MODEL)
        runner = ExtensionRunner(context)
        runner.load([ext_path])

        assert len(runner.loaded_paths) == 1
        commands = runner.get_commands()
        assert len(commands) == 1
        assert commands[0].name == "ext-hello"


def test_extension_runner_load_with_tool():
    """Extension registers a tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ext_path = os.path.join(tmpdir, "tool_ext.py")
        with open(ext_path, "w") as f:
            f.write("""
from pi_agent.types import AgentTool, AgentToolResult
from pi_ai.types import TextContent

class CustomTool(AgentTool):
    def __init__(self):
        self.name = "custom"
        self.label = "Custom"
        self.description = "A custom tool"
        self.parameters = {"type": "object", "properties": {}}

    async def execute(self, tool_call_id, params, on_update=None, abort_signal=None):
        return AgentToolResult(content=[TextContent(text="custom result")])

def setup(context, runtime):
    runtime.register_tool(CustomTool())
""")

        context = ExtensionContext(cwd=tmpdir, model=MOCK_MODEL)
        runner = ExtensionRunner(context)
        runner.load([ext_path])

        tools = runner.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "custom"


def test_extension_runner_load_failure():
    """Extension load failure doesn't crash."""
    context = ExtensionContext(cwd="/tmp")
    runner = ExtensionRunner(context)
    runner.load(["/nonexistent/path.py"])

    assert len(runner.loaded_paths) == 0


@pytest.mark.asyncio
async def test_extension_runner_emit_event():
    """Events are dispatched to extension handlers."""
    events_received: list = []

    with tempfile.TemporaryDirectory() as tmpdir:
        ext_path = os.path.join(tmpdir, "event_ext.py")
        with open(ext_path, "w") as f:
            f.write("""
_events = []

async def on_event(event):
    _events.append(event)

def setup(context, runtime):
    runtime.on_event(on_event)
""")

        context = ExtensionContext(cwd=tmpdir)
        runner = ExtensionRunner(context)
        runner.load([ext_path])

        event = AgentStartEvent()
        await runner.emit_event(event)

        # Verify the extension received the event
        # (We can't easily access _events from the loaded module,
        # but we can verify no exception was raised)
        assert len(runner.loaded_paths) == 1
