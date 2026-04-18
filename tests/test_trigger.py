"""Unit tests for trigger.py - consolidated PreToolUse, Stop, and SubagentStop handler.

Tests internal functions directly (no subprocess), complementing the
subprocess-based integration tests in test_hooks.py.
"""

import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

# Make scripts/ importable so we can load trigger.py as a module.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
trigger = importlib.import_module("trigger")
sys.path.pop(0)


class TestGetMemoryFiles:
    """Tests for get_memory_files - resolves configured memory file names."""

    def test_returns_claude_md_when_key_absent(self):
        """Defaults to ['CLAUDE.md'] when memoryFiles not in config."""
        assert trigger.get_memory_files({}) == ["CLAUDE.md"]

    def test_returns_claude_md_when_empty_list(self):
        """Falls back to ['CLAUDE.md'] when memoryFiles is an empty list."""
        assert trigger.get_memory_files({"memoryFiles": []}) == ["CLAUDE.md"]

    def test_returns_list_as_is(self):
        """Returns list unchanged when memoryFiles is already a list."""
        assert trigger.get_memory_files({"memoryFiles": ["AGENTS.md"]}) == ["AGENTS.md"]

    def test_returns_both_when_both(self):
        """Returns both names when both are configured."""
        result = trigger.get_memory_files({"memoryFiles": ["CLAUDE.md", "AGENTS.md"]})
        assert result == ["CLAUDE.md", "AGENTS.md"]

    def test_wraps_string_in_list(self):
        """Wraps a bare string value in a list for backwards compatibility."""
        assert trigger.get_memory_files({"memoryFiles": "CLAUDE.md"}) == ["CLAUDE.md"]


class TestGetActiveMemoryFile:
    """Tests for get_active_memory_file - selects the file that gets full content."""

    def test_returns_agents_when_agents_present(self):
        """AGENTS.md wins when only AGENTS.md configured."""
        assert trigger.get_active_memory_file(["AGENTS.md"]) == "AGENTS.md"

    def test_returns_agents_when_both(self):
        """AGENTS.md wins when both CLAUDE.md and AGENTS.md configured."""
        assert trigger.get_active_memory_file(["CLAUDE.md", "AGENTS.md"]) == "AGENTS.md"

    def test_returns_claude_when_only_claude(self):
        """CLAUDE.md returned when it is the only configured file."""
        assert trigger.get_active_memory_file(["CLAUDE.md"]) == "CLAUDE.md"


class TestDirtyFilePath:
    """Tests for dirty_file_path - returns session-specific or default dirty-files path."""

    def test_returns_session_specific_path(self, tmp_path):
        """With session_id, returns dirty-files-{session_id}."""
        result = trigger.dirty_file_path(str(tmp_path), "abc-123")
        expected = Path(tmp_path) / ".claude" / "auto-memory" / "dirty-files-abc-123"
        assert result == expected

    def test_returns_default_path_without_session(self, tmp_path):
        """Without session_id, returns plain dirty-files."""
        result = trigger.dirty_file_path(str(tmp_path))
        expected = Path(tmp_path) / ".claude" / "auto-memory" / "dirty-files"
        assert result == expected

    def test_returns_default_path_with_empty_session(self, tmp_path):
        """Empty string session_id returns plain dirty-files."""
        result = trigger.dirty_file_path(str(tmp_path), "")
        expected = Path(tmp_path) / ".claude" / "auto-memory" / "dirty-files"
        assert result == expected


class TestLoadConfig:
    """Tests for load_config - reads plugin configuration."""

    def test_returns_default_when_no_config(self, tmp_path):
        """Returns default triggerMode when config file is missing."""
        config = trigger.load_config(str(tmp_path))
        assert config == {"triggerMode": "default"}

    def test_reads_valid_config(self, tmp_path):
        """Reads and returns existing config file."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "gitmode"}))

        config = trigger.load_config(str(tmp_path))
        assert config["triggerMode"] == "gitmode"

    def test_returns_default_on_invalid_json(self, tmp_path):
        """Returns default when config file has invalid JSON."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text("not json{{{")

        config = trigger.load_config(str(tmp_path))
        assert config == {"triggerMode": "default"}

    def test_preserves_extra_fields(self, tmp_path):
        """Preserves extra fields in config beyond triggerMode."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(
            json.dumps({"triggerMode": "gitmode", "customField": "value"})
        )

        config = trigger.load_config(str(tmp_path))
        assert config["customField"] == "value"

    def test_default_auto_commit_false(self, tmp_path):
        """Default config does not include autoCommit (treated as false)."""
        config = trigger.load_config(str(tmp_path))
        assert config.get("autoCommit", False) is False

    def test_default_auto_push_false(self, tmp_path):
        """Default config does not include autoPush (treated as false)."""
        config = trigger.load_config(str(tmp_path))
        assert config.get("autoPush", False) is False

    def test_reads_auto_commit_config(self, tmp_path):
        """Reads autoCommit and autoPush from config file."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(
            json.dumps({"triggerMode": "default", "autoCommit": True, "autoPush": True})
        )

        config = trigger.load_config(str(tmp_path))
        assert config["autoCommit"] is True
        assert config["autoPush"] is True


class TestPluginInitialized:
    """Tests for plugin_initialized - opt-in guard for uninitialized projects (#17)."""

    def test_returns_false_when_config_absent(self, tmp_path):
        """Returns False when config.json does not exist."""
        assert trigger.plugin_initialized(str(tmp_path)) is False

    def test_returns_true_when_config_present(self, tmp_path):
        """Returns True when config.json exists."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))

        assert trigger.plugin_initialized(str(tmp_path)) is True

    def test_returns_false_when_only_dirty_files_present(self, tmp_path):
        """Returns False when dirty-files exists but config.json does not."""
        dirty_dir = tmp_path / ".claude" / "auto-memory"
        dirty_dir.mkdir(parents=True)
        (dirty_dir / "dirty-files").write_text("/file.py\n")

        assert trigger.plugin_initialized(str(tmp_path)) is False


class TestReadDirtyFiles:
    """Tests for read_dirty_files - reads and deduplicates dirty file list."""

    def test_returns_empty_when_no_file(self, tmp_path):
        """Returns empty list when dirty-files doesn't exist."""
        files = trigger.read_dirty_files(str(tmp_path))
        assert files == []

    def test_returns_empty_when_file_empty(self, tmp_path):
        """Returns empty list when dirty-files is empty."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("")

        files = trigger.read_dirty_files(str(tmp_path))
        assert files == []

    def test_reads_file_paths(self, tmp_path):
        """Reads file paths from dirty-files."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/src/main.py\n/src/util.py\n")

        files = trigger.read_dirty_files(str(tmp_path))
        assert files == ["/src/main.py", "/src/util.py"]

    def test_deduplicates_paths(self, tmp_path):
        """Removes duplicate file paths."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/file.py\n/file.py\n/file.py\n")

        files = trigger.read_dirty_files(str(tmp_path))
        assert files == ["/file.py"]

    def test_strips_commit_context(self, tmp_path):
        """Strips inline commit context [hash: message] from paths."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/src/main.py [abc1234: Add feature]\n")

        files = trigger.read_dirty_files(str(tmp_path))
        assert files == ["/src/main.py"]

    def test_limits_to_20_files(self, tmp_path):
        """Caps file list at 20 entries."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        lines = [f"/file{i:03d}.py" for i in range(30)]
        dirty.write_text("\n".join(lines) + "\n")

        files = trigger.read_dirty_files(str(tmp_path))
        assert len(files) == 20

    def test_sorted_output(self, tmp_path):
        """Returns files in sorted order."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/z.py\n/a.py\n/m.py\n")

        files = trigger.read_dirty_files(str(tmp_path))
        assert files == ["/a.py", "/m.py", "/z.py"]

    def test_skips_blank_lines(self, tmp_path):
        """Ignores blank lines in dirty-files."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/a.py\n\n\n/b.py\n\n")

        files = trigger.read_dirty_files(str(tmp_path))
        assert files == ["/a.py", "/b.py"]

    def test_reads_session_specific_file(self, tmp_path):
        """Reads from dirty-files-{session_id} when session_id provided."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)
        (session_dir / "dirty-files-sess-001").write_text("/src/a.py\n")
        # Also create a plain dirty-files with different content
        (session_dir / "dirty-files").write_text("/src/b.py\n")

        files = trigger.read_dirty_files(str(tmp_path), session_id="sess-001")
        assert files == ["/src/a.py"]

    def test_ignores_other_session_files(self, tmp_path):
        """Only reads own session's file, not other sessions'."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)
        (session_dir / "dirty-files-sess-001").write_text("/src/a.py\n")
        (session_dir / "dirty-files-sess-002").write_text("/src/b.py\n")

        files = trigger.read_dirty_files(str(tmp_path), session_id="sess-001")
        assert files == ["/src/a.py"]
        assert "/src/b.py" not in files


class TestBuildSpawnReason:
    """Tests for build_spawn_reason - constructs agent spawn instruction."""

    def test_includes_file_list(self):
        """Spawn reason includes the file paths."""
        reason = trigger.build_spawn_reason(["/src/main.py", "/src/util.py"])
        assert "/src/main.py" in reason
        assert "/src/util.py" in reason

    def test_includes_task_tool_params(self):
        """Spawn reason includes required Task tool parameters."""
        reason = trigger.build_spawn_reason(["/file.py"])
        assert "run_in_background" in reason
        assert "bypassPermissions" in reason
        assert "memory-updater" in reason

    def test_includes_read_instruction(self):
        """Spawn reason tells Claude to re-read CLAUDE.md after agent completes."""
        reason = trigger.build_spawn_reason(["/file.py"])
        assert "Read tool" in reason
        assert "CLAUDE.md" in reason

    def test_prompt_references_active_file_claude(self):
        """Without memoryFiles config, prompt references CLAUDE.md."""
        reason = trigger.build_spawn_reason(["/file.py"], {})
        assert "Update CLAUDE.md" in reason

    def test_prompt_references_active_file_agents(self):
        """With AGENTS.md configured, prompt references AGENTS.md."""
        reason = trigger.build_spawn_reason(["/file.py"], {"memoryFiles": ["AGENTS.md"]})
        assert "Update AGENTS.md" in reason

    def test_read_instruction_references_active_file(self):
        """With AGENTS.md configured, Read instruction mentions AGENTS.md."""
        reason = trigger.build_spawn_reason(["/file.py"], {"memoryFiles": ["AGENTS.md"]})
        assert "AGENTS.md" in reason
        assert "Read tool" in reason


class TestHandleStop:
    """Tests for handle_stop - Stop hook event handler."""

    def test_no_output_when_no_dirty_files(self, tmp_path, capsys):
        """No output when dirty-files is empty or missing."""
        trigger.handle_stop({}, str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_no_output_when_stop_hook_active(self, tmp_path, capsys):
        """No output when stop_hook_active prevents infinite loop."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/file.py\n")

        trigger.handle_stop({"stop_hook_active": True}, str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_blocks_with_dirty_files(self, tmp_path, capsys):
        """Outputs block decision when dirty files exist."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty = config_dir / "dirty-files"
        dirty.write_text("/src/main.py\n")

        trigger.handle_stop({}, str(tmp_path))
        output = json.loads(capsys.readouterr().out)
        assert output["decision"] == "block"
        assert "/src/main.py" in output["reason"]

    def test_works_in_gitmode(self, tmp_path, capsys):
        """Stop handler still fires in gitmode (safety net for last commit)."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "gitmode"}))
        (config_dir / "dirty-files").write_text("/file.py\n")

        trigger.handle_stop({}, str(tmp_path))
        output = json.loads(capsys.readouterr().out)
        assert output["decision"] == "block"

    def test_no_output_when_not_initialized(self, tmp_path, capsys):
        """No output when config.json is absent, even with dirty files (#17)."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/src/main.py\n")

        trigger.handle_stop({}, str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_reads_session_specific_dirty_files(self, tmp_path, capsys):
        """Passes session_id through to read session-specific dirty-files."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        # Session-specific file has content, plain file does not
        (config_dir / "dirty-files-sess-xyz").write_text("/src/main.py\n")

        trigger.handle_stop({"session_id": "sess-xyz"}, str(tmp_path))
        output = json.loads(capsys.readouterr().out)
        assert output["decision"] == "block"
        assert "/src/main.py" in output["reason"]


class TestHandlePreToolUse:
    """Tests for handle_pre_tool_use - PreToolUse hook event handler."""

    def _setup_gitmode(self, tmp_path):
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "gitmode"}))

    def test_no_output_in_default_mode(self, tmp_path, capsys):
        """No output in default trigger mode (PreToolUse only active in gitmode)."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/file.py\n")

        input_data = {
            "hook_event_name": "PreToolUse",
            "tool_input": {"command": "git commit -m 'test'"},
        }
        trigger.handle_pre_tool_use(input_data, str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_no_output_for_non_git_commit(self, tmp_path, capsys):
        """No output for non-git-commit commands in gitmode."""
        self._setup_gitmode(tmp_path)
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.write_text("/file.py\n")

        input_data = {
            "hook_event_name": "PreToolUse",
            "tool_input": {"command": "git status"},
        }
        trigger.handle_pre_tool_use(input_data, str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_no_output_when_no_dirty_files(self, tmp_path, capsys):
        """No output when no dirty files even with git commit in gitmode."""
        self._setup_gitmode(tmp_path)

        input_data = {
            "hook_event_name": "PreToolUse",
            "tool_input": {"command": "git commit -m 'test'"},
        }
        trigger.handle_pre_tool_use(input_data, str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_denies_git_commit_with_dirty_files(self, tmp_path, capsys):
        """Denies git commit in gitmode when dirty files exist."""
        self._setup_gitmode(tmp_path)
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.write_text("/src/feature.py\n")

        input_data = {
            "hook_event_name": "PreToolUse",
            "tool_input": {"command": "git commit -m 'Add feature'"},
        }
        trigger.handle_pre_tool_use(input_data, str(tmp_path))

        output = json.loads(capsys.readouterr().out)
        hook_output = output["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "deny"
        assert "/src/feature.py" in hook_output["permissionDecisionReason"]

    def test_no_output_when_not_initialized(self, tmp_path, capsys):
        """No output when config.json is absent, even for git commit (#17)."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/src/feature.py\n")

        input_data = {
            "hook_event_name": "PreToolUse",
            "tool_input": {"command": "git commit -m 'test'"},
        }
        trigger.handle_pre_tool_use(input_data, str(tmp_path))
        assert capsys.readouterr().out == ""


class TestEventRouting:
    """Tests for main() event routing - the core consolidation logic.

    Verifies that trigger.py correctly routes to handle_stop or
    handle_pre_tool_use based on hook_event_name in stdin JSON.
    """

    def test_routes_stop_event(self, tmp_path):
        """Routes to handle_stop when hook_event_name is Stop."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty = config_dir / "dirty-files"
        dirty.write_text("/file.py\n")

        stdin_data = json.dumps({"hook_event_name": "Stop"})
        with (
            patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_path)}),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.read.return_value = stdin_data
            trigger.main()

            mock_print.assert_called_once()
            output = json.loads(mock_print.call_args[0][0])
            assert output["decision"] == "block"

    def test_routes_pre_tool_use_event(self, tmp_path):
        """Routes to handle_pre_tool_use when hook_event_name is PreToolUse."""
        # Set up gitmode so PreToolUse actually does something
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "gitmode"}))
        (config_dir / "dirty-files").write_text("/file.py\n")

        stdin_data = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_input": {"command": "git commit -m 'test'"},
            }
        )
        with (
            patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_path)}),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.read.return_value = stdin_data
            trigger.main()

            mock_print.assert_called_once()
            output = json.loads(mock_print.call_args[0][0])
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_defaults_to_stop_when_no_event_name(self, tmp_path):
        """Defaults to Stop handler when hook_event_name is missing."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty = config_dir / "dirty-files"
        dirty.write_text("/file.py\n")

        with (
            patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_path)}),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.read.return_value = "{}"
            trigger.main()

            output = json.loads(mock_print.call_args[0][0])
            assert output["decision"] == "block"

    def test_exits_silently_without_project_dir(self):
        """Exits without output when CLAUDE_PROJECT_DIR is not set."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.read.return_value = "{}"
            trigger.main()
            mock_print.assert_not_called()

    def test_routes_subagent_stop_event(self, tmp_path):
        """Routes to handle_subagent_stop when hook_event_name is SubagentStop."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        (config_dir / "dirty-files").write_text("/file.py\n")

        stdin_data = json.dumps({"hook_event_name": "SubagentStop"})
        with (
            patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_path)}),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.read.return_value = stdin_data
            trigger.main()

            # SubagentStop produces no output, just clears dirty-files
            mock_print.assert_not_called()

        dirty = config_dir / "dirty-files"
        assert dirty.read_text() == ""

    def test_routes_subagent_stop_with_session_id(self, tmp_path):
        """SubagentStop passes input_data (including session_id) to handler."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        (config_dir / "dirty-files-sess-route").write_text("/file.py\n")
        # Plain dirty-files should NOT be touched
        (config_dir / "dirty-files").write_text("/other.py\n")

        stdin_data = json.dumps(
            {
                "hook_event_name": "SubagentStop",
                "session_id": "sess-route",
            }
        )
        with (
            patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_path)}),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.read.return_value = stdin_data
            trigger.main()
            mock_print.assert_not_called()

        assert (config_dir / "dirty-files-sess-route").read_text() == ""
        assert (config_dir / "dirty-files").read_text() == "/other.py\n"


class TestClearDirtyFiles:
    """Tests for clear_dirty_files - truncates dirty-files."""

    def test_clears_existing_file(self, tmp_path):
        """Truncates dirty-files when it exists with content."""
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty.parent.mkdir(parents=True)
        dirty.write_text("/src/main.py\n/src/util.py\n")

        trigger.clear_dirty_files(str(tmp_path))
        assert dirty.read_text() == ""

    def test_noop_when_file_missing(self, tmp_path):
        """Does nothing when dirty-files doesn't exist."""
        trigger.clear_dirty_files(str(tmp_path))
        dirty = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert not dirty.exists()

    def test_clears_session_specific_file(self, tmp_path):
        """Clears only dirty-files-{session_id} when session_id provided."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)
        (session_dir / "dirty-files-sess-001").write_text("/src/a.py\n")
        (session_dir / "dirty-files-sess-002").write_text("/src/b.py\n")

        trigger.clear_dirty_files(str(tmp_path), session_id="sess-001")
        assert (session_dir / "dirty-files-sess-001").read_text() == ""
        assert (session_dir / "dirty-files-sess-002").read_text() == "/src/b.py\n"

    def test_leaves_other_session_files(self, tmp_path):
        """Other sessions' dirty-files are untouched when clearing with session_id."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)
        (session_dir / "dirty-files-sess-A").write_text("/a.py\n")
        (session_dir / "dirty-files-sess-B").write_text("/b.py\n")
        (session_dir / "dirty-files").write_text("/c.py\n")

        trigger.clear_dirty_files(str(tmp_path), session_id="sess-A")
        assert (session_dir / "dirty-files-sess-A").read_text() == ""
        assert (session_dir / "dirty-files-sess-B").read_text() == "/b.py\n"
        assert (session_dir / "dirty-files").read_text() == "/c.py\n"


class TestHandleSubagentStop:
    """Tests for handle_subagent_stop - SubagentStop hook event handler."""

    def test_clears_when_config_and_dirty_files_present(self, tmp_path):
        """Clears dirty-files when config.json and dirty-files both exist."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty = config_dir / "dirty-files"
        dirty.write_text("/src/main.py\n/src/util.py\n")

        trigger.handle_subagent_stop({}, str(tmp_path))
        assert dirty.read_text() == ""

    def test_clears_even_when_config_missing(self, tmp_path):
        """Still clears dirty-files when config.json is missing (#17, #25).

        Regression gate: the previous early-return guard caused an
        infinite Stop-hook loop on uninitialized projects, because
        dirty-files was never cleaned up and the Stop hook kept firing.
        """
        dirty_dir = tmp_path / ".claude" / "auto-memory"
        dirty_dir.mkdir(parents=True)
        dirty = dirty_dir / "dirty-files"
        dirty.write_text("/file.py\n")

        trigger.handle_subagent_stop({}, str(tmp_path))
        assert dirty.read_text() == ""

    def test_noop_when_dirty_files_empty(self, tmp_path):
        """Does nothing when dirty-files is empty (nothing to clean up)."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty = config_dir / "dirty-files"
        dirty.write_text("")

        trigger.handle_subagent_stop({}, str(tmp_path))
        assert dirty.read_text() == ""

    def test_noop_when_dirty_files_missing(self, tmp_path):
        """Does nothing when dirty-files doesn't exist."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))

        trigger.handle_subagent_stop({}, str(tmp_path))
        dirty = config_dir / "dirty-files"
        assert not dirty.exists()

    def test_no_output(self, tmp_path, capsys):
        """SubagentStop handler produces no stdout output."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        (config_dir / "dirty-files").write_text("/file.py\n")

        trigger.handle_subagent_stop({}, str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_clears_session_specific_file(self, tmp_path):
        """Clears only own session's dirty-files when session_id provided."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        (config_dir / "dirty-files-sess-A").write_text("/a.py\n")
        (config_dir / "dirty-files-sess-B").write_text("/b.py\n")

        trigger.handle_subagent_stop({"session_id": "sess-A"}, str(tmp_path))
        assert (config_dir / "dirty-files-sess-A").read_text() == ""
        assert (config_dir / "dirty-files-sess-B").read_text() == "/b.py\n"


class TestCleanupStaleSessions:
    """Tests for cleanup_stale_session_files - removes orphaned session dirty-files."""

    def test_removes_old_session_files(self, tmp_path):
        """Removes session-specific dirty-files older than max_age_hours."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)
        stale = session_dir / "dirty-files-old-session"
        stale.write_text("/stale.py\n")
        # Set mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        os.utime(stale, (old_time, old_time))

        trigger.cleanup_stale_session_files(str(tmp_path), max_age_hours=24)
        assert not stale.exists()

    def test_keeps_recent_session_files(self, tmp_path):
        """Keeps session-specific dirty-files younger than max_age_hours."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)
        recent = session_dir / "dirty-files-recent-session"
        recent.write_text("/recent.py\n")
        # mtime is now (just created), well within 24h

        trigger.cleanup_stale_session_files(str(tmp_path), max_age_hours=24)
        assert recent.exists()
        assert recent.read_text() == "/recent.py\n"

    def test_keeps_plain_dirty_files(self, tmp_path):
        """Never removes the legacy plain dirty-files (no session suffix)."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)
        plain = session_dir / "dirty-files"
        plain.write_text("/legacy.py\n")
        # Make it old
        old_time = time.time() - (48 * 3600)
        os.utime(plain, (old_time, old_time))

        trigger.cleanup_stale_session_files(str(tmp_path), max_age_hours=24)
        assert plain.exists()
        assert plain.read_text() == "/legacy.py\n"

    def test_noop_when_no_session_files(self, tmp_path):
        """No crash when directory has no session files."""
        session_dir = tmp_path / ".claude" / "auto-memory"
        session_dir.mkdir(parents=True)

        trigger.cleanup_stale_session_files(str(tmp_path), max_age_hours=24)
        # Should not raise

    def test_noop_when_directory_missing(self, tmp_path):
        """No crash when .claude/auto-memory directory doesn't exist."""
        trigger.cleanup_stale_session_files(str(tmp_path), max_age_hours=24)
        # Should not raise


class TestAutoCommitMemoryFiles:
    """Tests for auto_commit_memory_files - stages and commits memory files."""

    def _init_git_repo(self, tmp_path):
        """Initialize a git repo with an initial commit."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )
        init_file = tmp_path / ".gitkeep"
        init_file.write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

    def test_commits_modified_claude_md(self, tmp_path):
        """Stages and commits modified CLAUDE.md files."""
        self._init_git_repo(tmp_path)
        # Create and commit CLAUDE.md initially
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Initial")
        subprocess.run(["git", "add", "CLAUDE.md"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add CLAUDE.md"],
            cwd=tmp_path,
            capture_output=True,
        )
        # Modify CLAUDE.md (simulating memory-updater)
        claude_md.write_text("# Updated by auto-memory")

        claude_config: dict[str, Any] = {"triggerMode": "default"}
        result = trigger.auto_commit_memory_files(str(tmp_path), claude_config)
        assert result is True

        # Verify commit was made
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert "CLAUDE.md" in log.stdout
        assert "[auto-memory]" in log.stdout

    def test_noop_when_no_claude_md_changes(self, tmp_path):
        """Returns False when no CLAUDE.md files are modified."""
        self._init_git_repo(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Clean")
        subprocess.run(["git", "add", "CLAUDE.md"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add CLAUDE.md"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = trigger.auto_commit_memory_files(str(tmp_path), {})
        assert result is False

    def test_commit_message_format(self, tmp_path):
        """Commit message is 'chore: update CLAUDE.md [auto-memory]' for default config."""
        self._init_git_repo(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Initial")
        subprocess.run(["git", "add", "CLAUDE.md"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add CLAUDE.md"],
            cwd=tmp_path,
            capture_output=True,
        )
        claude_md.write_text("# Updated")

        trigger.auto_commit_memory_files(str(tmp_path), {})

        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert log.stdout.strip() == "chore: update CLAUDE.md [auto-memory]"

    def test_only_commits_claude_md_files(self, tmp_path):
        """Other modified files are not included in the commit."""
        self._init_git_repo(tmp_path)
        # Create and commit both files
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Initial")
        other = tmp_path / "other.py"
        other.write_text("# other")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add files"],
            cwd=tmp_path,
            capture_output=True,
        )
        # Modify both
        claude_md.write_text("# Updated")
        other.write_text("# modified")

        trigger.auto_commit_memory_files(str(tmp_path), {})

        # other.py should still show as modified (not committed)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert "other.py" in status.stdout

    def test_returns_false_on_git_failure(self, tmp_path):
        """Returns False when not in a git repo (graceful failure)."""
        # tmp_path is not a git repo
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Not a repo")

        result = trigger.auto_commit_memory_files(str(tmp_path), {})
        assert result is False

    def test_commits_subtree_claude_md(self, tmp_path):
        """Commits CLAUDE.md files in subdirectories too."""
        self._init_git_repo(tmp_path)
        # Create root and subtree CLAUDE.md
        root_md = tmp_path / "CLAUDE.md"
        root_md.write_text("# Root")
        sub_dir = tmp_path / "src"
        sub_dir.mkdir()
        sub_md = sub_dir / "CLAUDE.md"
        sub_md.write_text("# Sub")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add CLAUDE.md files"],
            cwd=tmp_path,
            capture_output=True,
        )
        # Modify both
        root_md.write_text("# Root updated")
        sub_md.write_text("# Sub updated")

        result = trigger.auto_commit_memory_files(str(tmp_path), {})
        assert result is True

        # Both should be committed
        show = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert "CLAUDE.md" in show.stdout
        assert "src/CLAUDE.md" in show.stdout

    def test_commits_agents_md_when_configured(self, tmp_path):
        """Commits AGENTS.md when memoryFiles is set to AGENTS.md."""
        self._init_git_repo(tmp_path)
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Initial")
        subprocess.run(["git", "add", "AGENTS.md"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add AGENTS.md"],
            cwd=tmp_path,
            capture_output=True,
        )
        agents_md.write_text("# Updated by auto-memory")

        config: dict[str, Any] = {"memoryFiles": ["AGENTS.md"]}
        result = trigger.auto_commit_memory_files(str(tmp_path), config)
        assert result is True

        show = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert "AGENTS.md" in show.stdout

    def test_commits_both_when_both_configured(self, tmp_path):
        """Commits both CLAUDE.md and AGENTS.md in a single commit."""
        self._init_git_repo(tmp_path)
        (tmp_path / "CLAUDE.md").write_text("# Redirect")
        (tmp_path / "AGENTS.md").write_text("# Initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add memory files"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "CLAUDE.md").write_text("# Redirect v2")
        (tmp_path / "AGENTS.md").write_text("# Updated")

        config = {"memoryFiles": ["CLAUDE.md", "AGENTS.md"]}
        result = trigger.auto_commit_memory_files(str(tmp_path), config)
        assert result is True

        show = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert "CLAUDE.md" in show.stdout
        assert "AGENTS.md" in show.stdout

    def test_does_not_commit_non_memory_file(self, tmp_path):
        """CLAUDE.md is not committed when only AGENTS.md is configured."""
        self._init_git_repo(tmp_path)
        (tmp_path / "CLAUDE.md").write_text("# Read AGENTS.md")
        (tmp_path / "AGENTS.md").write_text("# Initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add files"],
            cwd=tmp_path,
            capture_output=True,
        )
        # Only CLAUDE.md modified; AGENTS.md not modified
        (tmp_path / "CLAUDE.md").write_text("# Modified redirect")

        config = {"memoryFiles": ["AGENTS.md"]}
        result = trigger.auto_commit_memory_files(str(tmp_path), config)
        assert result is False  # CLAUDE.md not in memoryFiles, nothing to commit

    def test_commit_message_generic_when_agents_involved(self, tmp_path):
        """Commit message is generic when AGENTS.md is in memoryFiles."""
        self._init_git_repo(tmp_path)
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Initial")
        subprocess.run(["git", "add", "AGENTS.md"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add AGENTS.md"],
            cwd=tmp_path,
            capture_output=True,
        )
        agents_md.write_text("# Updated")

        trigger.auto_commit_memory_files(str(tmp_path), {"memoryFiles": ["AGENTS.md"]})

        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert log.stdout.strip() == "chore: update memory files [auto-memory]"

    def test_returns_false_when_no_matching_files_modified(self, tmp_path):
        """Returns False when only non-configured memory files are modified."""
        self._init_git_repo(tmp_path)
        (tmp_path / "AGENTS.md").write_text("# Initial")
        (tmp_path / "CLAUDE.md").write_text("# Initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add files"],
            cwd=tmp_path,
            capture_output=True,
        )
        # Modify CLAUDE.md but config only tracks AGENTS.md
        (tmp_path / "CLAUDE.md").write_text("# Modified")

        result = trigger.auto_commit_memory_files(str(tmp_path), {"memoryFiles": ["AGENTS.md"]})
        assert result is False

    def test_commits_subtree_agents_md(self, tmp_path):
        """Commits AGENTS.md files in subdirectories too."""
        self._init_git_repo(tmp_path)
        root_agents = tmp_path / "AGENTS.md"
        root_agents.write_text("# Root")
        sub_dir = tmp_path / "src"
        sub_dir.mkdir()
        sub_agents = sub_dir / "AGENTS.md"
        sub_agents.write_text("# Sub")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add AGENTS.md files"],
            cwd=tmp_path,
            capture_output=True,
        )
        root_agents.write_text("# Root updated")
        sub_agents.write_text("# Sub updated")

        result = trigger.auto_commit_memory_files(str(tmp_path), {"memoryFiles": ["AGENTS.md"]})
        assert result is True

        show = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert "AGENTS.md" in show.stdout
        assert "src/AGENTS.md" in show.stdout


class TestAutoPush:
    """Tests for auto_push - pushes current branch to remote."""

    def test_returns_false_on_push_failure(self, tmp_path):
        """Returns False when push fails (no remote configured)."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / ".gitkeep").write_text("")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = trigger.auto_push(str(tmp_path))
        assert result is False

    def test_returns_false_when_not_git_repo(self, tmp_path):
        """Returns False when not in a git repo."""
        result = trigger.auto_push(str(tmp_path))
        assert result is False
