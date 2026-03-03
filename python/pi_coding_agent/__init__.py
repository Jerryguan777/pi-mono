"""pi_coding_agent — Coding agent with system prompt, model registry, settings, and execution modes."""

from pi_coding_agent.auth_storage import AuthStorage
from pi_coding_agent.extensions import ExtensionContext, ExtensionRunner, ExtensionRuntime
from pi_coding_agent.model_registry import ModelRegistry
from pi_coding_agent.resource_loader import ContextFile, load_project_context_files
from pi_coding_agent.settings_manager import Settings, SettingsManager
from pi_coding_agent.skills import Skill, format_skills_for_prompt, load_skills
from pi_coding_agent.slash_commands import SlashCommand, get_builtin_commands, parse_slash_command
from pi_coding_agent.system_prompt import build_system_prompt
