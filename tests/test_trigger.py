"""Unit tests for trigger.py - consolidated PreToolUse, Stop, and SubagentStop handler.

Tests internal functions directly (no subprocess), complementing the
subprocess-based integration tests in test_hooks.py.
"""

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

# Import trigger.py module
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

trigger = importlib.import_module("trigger")
sys.path.pop(0)


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


class TestHandleSubagentStop:
    """Tests for handle_subagent_stop - SubagentStop hook event handler."""

    def test_clears_when_config_and_dirty_files_present(self, tmp_path):
        """Clears dirty-files when config.json and dirty-files both exist."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty = config_dir / "dirty-files"
        dirty.write_text("/src/main.py\n/src/util.py\n")

        trigger.handle_subagent_stop(str(tmp_path))
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

        trigger.handle_subagent_stop(str(tmp_path))
        assert dirty.read_text() == ""

    def test_noop_when_dirty_files_empty(self, tmp_path):
        """Does nothing when dirty-files is empty (nothing to clean up)."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty = config_dir / "dirty-files"
        dirty.write_text("")

        trigger.handle_subagent_stop(str(tmp_path))
        assert dirty.read_text() == ""

    def test_noop_when_dirty_files_missing(self, tmp_path):
        """Does nothing when dirty-files doesn't exist."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))

        trigger.handle_subagent_stop(str(tmp_path))
        dirty = config_dir / "dirty-files"
        assert not dirty.exists()

    def test_no_output(self, tmp_path, capsys):
        """SubagentStop handler produces no stdout output."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        (config_dir / "dirty-files").write_text("/file.py\n")

        trigger.handle_subagent_stop(str(tmp_path))
        assert capsys.readouterr().out == ""
