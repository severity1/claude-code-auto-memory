"""Integration tests for auto-memory plugin."""

import json
import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent


def parse_markdown_frontmatter(file_path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    content = file_path.read_text()
    if not content.startswith("---"):
        return {}

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}

    yaml_content = content[3:end_idx].strip()
    return yaml.safe_load(yaml_content) or {}


class TestPluginConfiguration:
    """Tests for plugin.json configuration."""

    @pytest.fixture
    def plugin_json(self):
        path = PROJECT_ROOT / ".claude-plugin" / "plugin.json"
        return json.loads(path.read_text())

    def test_plugin_json_exists(self):
        """plugin.json exists."""
        assert (PROJECT_ROOT / ".claude-plugin" / "plugin.json").exists()

    def test_plugin_json_valid(self, plugin_json):
        """plugin.json is valid JSON with required fields."""
        assert "name" in plugin_json
        assert "description" in plugin_json
        assert "version" in plugin_json

    def test_plugin_name(self, plugin_json):
        """Plugin has correct name."""
        assert plugin_json["name"] == "auto-memory"

    def test_plugin_version_format(self, plugin_json):
        """Version follows semver format."""
        version = plugin_json["version"]
        assert re.match(r"^\d+\.\d+\.\d+$", version)


class TestHooksConfiguration:
    """Tests for hooks.json configuration."""

    @pytest.fixture
    def hooks_json(self):
        path = PROJECT_ROOT / "hooks" / "hooks.json"
        return json.loads(path.read_text())

    def test_hooks_json_exists(self):
        """hooks.json exists."""
        assert (PROJECT_ROOT / "hooks" / "hooks.json").exists()

    def test_hooks_json_valid(self, hooks_json):
        """hooks.json is valid JSON with hooks key."""
        assert "hooks" in hooks_json

    def test_has_post_tool_use_hook(self, hooks_json):
        """PostToolUse hook is configured."""
        assert "PostToolUse" in hooks_json["hooks"]

    def test_has_stop_hook(self, hooks_json):
        """Stop hook is configured."""
        assert "Stop" in hooks_json["hooks"]

    def test_has_pre_tool_use_hook(self, hooks_json):
        """PreToolUse hook is configured."""
        assert "PreToolUse" in hooks_json["hooks"]

    def test_pre_tool_use_matcher(self, hooks_json):
        """PreToolUse hook has Bash matcher."""
        pre_tool_use = hooks_json["hooks"]["PreToolUse"][0]
        assert pre_tool_use["matcher"] == "Bash"

    def test_post_tool_use_matcher(self, hooks_json):
        """PostToolUse hook has Edit|Write|Bash matcher."""
        post_tool_use = hooks_json["hooks"]["PostToolUse"][0]
        assert post_tool_use["matcher"] == "Edit|Write|Bash"

    def test_has_subagent_stop_hook(self, hooks_json):
        """SubagentStop hook is configured."""
        assert "SubagentStop" in hooks_json["hooks"]

    def test_subagent_stop_matcher(self, hooks_json):
        """SubagentStop matcher catches both bare and plugin-qualified agent names.

        The regex matches both `memory-updater` and
        `auto-memory:memory-updater` so we're resilient to however
        Claude Code resolves plugin-scoped subagent names at runtime (#25).
        """
        subagent_stop = hooks_json["hooks"]["SubagentStop"][0]
        assert subagent_stop["matcher"] == "^(auto-memory:)?memory-updater$"

    def test_hook_commands_quote_plugin_root(self, hooks_json):
        """All hook commands quote ${CLAUDE_PLUGIN_ROOT} for Windows paths with spaces (#26).

        Unquoted `${CLAUDE_PLUGIN_ROOT}` breaks when the resolved path
        contains whitespace (e.g. `C:\\Users\\First Last\\...`) because
        the shell splits the path across multiple arguments.
        """
        for event_name, hook_list in hooks_json["hooks"].items():
            for entry in hook_list:
                for hook in entry["hooks"]:
                    command = hook.get("command", "")
                    if "${CLAUDE_PLUGIN_ROOT}" not in command:
                        continue
                    assert '"${CLAUDE_PLUGIN_ROOT}' in command, (
                        f"{event_name} hook command has unquoted ${{CLAUDE_PLUGIN_ROOT}}: {command}"
                    )


class TestAgentConfiguration:
    """Tests for agent definitions."""

    @pytest.fixture
    def agent_path(self):
        return PROJECT_ROOT / "agents" / "memory-updater.md"

    def test_agent_exists(self, agent_path):
        """Agent file exists."""
        assert agent_path.exists()

    def test_agent_yaml_valid(self, agent_path):
        """Agent has valid YAML frontmatter."""
        frontmatter = parse_markdown_frontmatter(agent_path)
        assert frontmatter is not None

    def test_agent_has_name(self, agent_path):
        """Agent has name field."""
        frontmatter = parse_markdown_frontmatter(agent_path)
        assert "name" in frontmatter
        assert frontmatter["name"] == "memory-updater"

    def test_agent_has_description(self, agent_path):
        """Agent has description field."""
        frontmatter = parse_markdown_frontmatter(agent_path)
        assert "description" in frontmatter

    def test_agent_uses_sonnet(self, agent_path):
        """Agent uses sonnet model (haiku doesn't support extended thinking)."""
        frontmatter = parse_markdown_frontmatter(agent_path)
        assert frontmatter.get("model") == "sonnet"


class TestCommandsConfiguration:
    """Tests for command definitions."""

    @pytest.fixture
    def commands_dir(self):
        return PROJECT_ROOT / "commands"

    def test_init_exists(self, commands_dir):
        """init command exists."""
        assert (commands_dir / "init.md").exists()

    def test_calibrate_exists(self, commands_dir):
        """calibrate command exists."""
        assert (commands_dir / "calibrate.md").exists()

    def test_status_exists(self, commands_dir):
        """status command exists."""
        assert (commands_dir / "status.md").exists()

    def test_commands_have_yaml(self, commands_dir):
        """All commands have valid YAML frontmatter."""
        for cmd_file in commands_dir.glob("*.md"):
            frontmatter = parse_markdown_frontmatter(cmd_file)
            assert "description" in frontmatter, f"{cmd_file.name} missing description"


class TestFileStructure:
    """Tests for overall file structure."""

    def test_scripts_directory_exists(self):
        """scripts/ directory exists."""
        assert (PROJECT_ROOT / "scripts").is_dir()

    def test_skills_directory_exists(self):
        """skills/ directory exists."""
        assert (PROJECT_ROOT / "skills").is_dir()

    def test_agents_directory_exists(self):
        """agents/ directory exists."""
        assert (PROJECT_ROOT / "agents").is_dir()

    def test_commands_directory_exists(self):
        """commands/ directory exists."""
        assert (PROJECT_ROOT / "commands").is_dir()

    def test_hooks_directory_exists(self):
        """hooks/ directory exists."""
        assert (PROJECT_ROOT / "hooks").is_dir()

    def test_post_tool_use_script_exists(self):
        """post-tool-use.py script exists."""
        assert (PROJECT_ROOT / "scripts" / "post-tool-use.py").exists()

    def test_trigger_script_exists(self):
        """trigger.py script exists."""
        assert (PROJECT_ROOT / "scripts" / "trigger.py").exists()

    def test_dev_marketplace_exists(self):
        """.dev-marketplace directory exists for local development."""
        assert (PROJECT_ROOT / ".dev-marketplace" / ".claude-plugin" / "marketplace.json").exists()

    def test_agents_root_template_exists(self):
        """AGENTS.root.md.template exists for AGENTS.md support (#14)."""
        assert (
            PROJECT_ROOT / "skills" / "codebase-analyzer" / "templates" / "AGENTS.root.md.template"
        ).exists()

    def test_agents_subtree_template_exists(self):
        """AGENTS.subtree.md.template exists for AGENTS.md support (#14)."""
        assert (
            PROJECT_ROOT
            / "skills"
            / "codebase-analyzer"
            / "templates"
            / "AGENTS.subtree.md.template"
        ).exists()

    def test_claude_redirect_template_exists(self):
        """CLAUDE.redirect.md.template exists for redirect mode (#14)."""
        assert (
            PROJECT_ROOT
            / "skills"
            / "codebase-analyzer"
            / "templates"
            / "CLAUDE.redirect.md.template"
        ).exists()
