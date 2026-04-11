"""Tests for hook scripts."""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


class TestPostToolUseHook:
    """Tests for post-tool-use.py hook."""

    def _init_config(self, tmp_path):
        """Create config.json so plugin_initialized() returns True."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))

    def _make_tool_input(self, file_path: str, tool_name: str = "Edit") -> str:
        """Create JSON input for post-tool-use hook (Edit/Write tools)."""
        return json.dumps(
            {
                "tool_name": tool_name,
                "tool_input": {"file_path": file_path},
            }
        )

    def _make_bash_input(self, command: str) -> str:
        """Create JSON input for Bash tool."""
        return json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": command},
            }
        )

    def test_creates_dirty_file(self, tmp_path):
        """Hook creates .claude/auto-memory/dirty-files if it doesn't exist."""
        self._init_config(tmp_path)
        file_path = str(tmp_path / "file.py")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()

    def test_appends_paths(self, tmp_path):
        """Hook appends file paths to dirty file."""
        self._init_config(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file = str(tmp_path / "existing" / "file.py")
        dirty_file.write_text(existing_file + "\n")

        new_file = str(tmp_path / "new" / "file.py")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(new_file),
            capture_output=True,
            text=True,
        )
        content = dirty_file.read_text()
        assert existing_file in content
        assert new_file in content

    def test_no_output(self, tmp_path):
        """Hook produces no output (zero token cost)."""
        self._init_config(tmp_path)
        file_path = str(tmp_path / "file.py")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        assert result.stdout == ""
        assert result.stderr == ""

    def test_handles_missing_input(self):
        """Hook exits gracefully when input is missing."""
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={},
            input="{}",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_excludes_claude_directory(self, tmp_path):
        """Hook excludes files in .claude/ directory."""
        self._init_config(tmp_path)
        file_path = str(tmp_path / ".claude" / "state.json")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert not dirty_file.exists()

    def test_excludes_claude_md(self, tmp_path):
        """Hook excludes CLAUDE.md files."""
        self._init_config(tmp_path)
        file_path = str(tmp_path / "CLAUDE.md")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert not dirty_file.exists()

    def test_excludes_files_outside_project(self, tmp_path):
        """Hook excludes files outside project directory."""
        file_path = "/outside/project/file.py"
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert not dirty_file.exists()

    # Bash command tracking tests

    def test_tracks_rm_command(self, tmp_path):
        """Hook tracks files from rm command."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm file.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "file.py" in content

    def test_tracks_rm_with_flags(self, tmp_path):
        """Hook tracks files from rm -rf command."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm -rf src/old_module"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "old_module" in content

    def test_tracks_rm_multiple_files(self, tmp_path):
        """Hook tracks multiple files from rm command."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm file1.py file2.py file3.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "file1.py" in content
        assert "file2.py" in content
        assert "file3.py" in content

    def test_tracks_git_rm_command(self, tmp_path):
        """Hook tracks files from git rm command."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("git rm obsolete.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "obsolete.py" in content

    def test_tracks_mv_source(self, tmp_path):
        """Hook tracks source file from mv command."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("mv old_name.py new_name.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "old_name.py" in content
        # Should NOT track destination
        assert content.count("new_name.py") == 0 or "old_name.py" in content

    def test_tracks_unlink_command(self, tmp_path):
        """Hook tracks files from unlink command."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("unlink temp.txt"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "temp.txt" in content

    def test_ignores_non_file_bash_commands(self, tmp_path):
        """Hook ignores Bash commands that don't modify files."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}

        # Test various non-file commands
        non_file_commands = [
            "git status",
            "ls -la",
            "cat file.py",
            "npm install",
            "python --version",
            "echo hello",
            "grep pattern file.py",
        ]

        for cmd in non_file_commands:
            subprocess.run(
                [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
                env={**os.environ, **env},
                input=self._make_bash_input(cmd),
                capture_output=True,
                text=True,
            )

        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert not dirty_file.exists()

    def test_bash_no_output(self, tmp_path):
        """Hook produces no output for Bash commands (zero token cost)."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm file.py"),
            capture_output=True,
            text=True,
        )
        assert result.stdout == ""
        assert result.stderr == ""

    def test_stops_at_shell_operators(self, tmp_path):
        """Hook stops parsing at shell operators like && || ; |."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}

        # Test && operator - should only track file.py, not 'echo' or 'done'
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm file.py && echo done"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "file.py" in content
        assert "echo" not in content
        assert "done" not in content
        assert "&&" not in content

    def test_stops_at_semicolon(self, tmp_path):
        """Hook stops parsing at semicolon operator."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm old.py ; ls -la"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        content = dirty_file.read_text()
        assert "old.py" in content
        assert "ls" not in content
        assert "-la" not in content

    def test_stops_at_pipe(self, tmp_path):
        """Hook stops parsing at pipe operator."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm -rf build | tee log.txt"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        content = dirty_file.read_text()
        assert "build" in content
        assert "tee" not in content
        assert "log.txt" not in content

    def test_stops_at_redirect(self, tmp_path):
        """Hook stops parsing at redirect operators."""
        self._init_config(tmp_path)
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm deleted.py > /dev/null"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        content = dirty_file.read_text()
        assert "deleted.py" in content
        assert "/dev/null" not in content

    def test_skip_git_commit_in_default_mode(self, tmp_path):
        """Hook skips git commit commands in default mode (files tracked via Edit/Write)."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("git commit -m 'Add feature'"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert not dirty_file.exists()

    def test_no_dirty_files_when_config_absent(self, tmp_path):
        """Hook does not write dirty-files when config.json is absent (#17).

        Projects without config.json have not run /auto-memory:init.
        The plugin must stay entirely inert on those projects.
        """
        file_path = str(tmp_path / "src" / "main.py")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        assert not dirty_file.exists()


class TestStopHook:
    """Tests for trigger.py Stop hook behavior."""

    def _init_config(self, tmp_path):
        """Create config.json so plugin_initialized() returns True."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))

    def test_passes_when_empty(self, tmp_path):
        """Hook passes through when no dirty files exist."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_passes_when_active(self, tmp_path):
        """Hook passes through when stop_hook_active is true."""
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input='{"stop_hook_active": true}',
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_blocks_with_files(self, tmp_path):
        """Hook blocks and outputs JSON when dirty files exist."""
        self._init_config(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["decision"] == "block"
        assert "memory-updater" in output["reason"]

    def test_json_format(self, tmp_path):
        """Hook output is valid JSON with required fields."""
        self._init_config(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        assert "decision" in output
        assert "reason" in output

    def test_deduplicates_files(self, tmp_path):
        """Hook deduplicates file paths in output."""
        self._init_config(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("/file.py\n/file.py\n/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        # Should only mention file once
        assert output["reason"].count("/file.py") == 1

    def test_limits_file_count(self, tmp_path):
        """Hook limits file list to 20 files max."""
        self._init_config(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        files = [f"/file{i}.py" for i in range(30)]
        dirty_file.write_text("\n".join(files) + "\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        # Extract the file list portion and count files
        reason = output["reason"]
        # Files are listed after "changed files: " and before the next sentence
        files_part = reason.split("changed files: ")[1].split("'.")[0]
        file_count = files_part.count(",") + 1
        assert file_count <= 20

    def test_handles_invalid_json_input(self, tmp_path):
        """Hook handles invalid JSON input gracefully."""
        self._init_config(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="not valid json",
            capture_output=True,
            text=True,
        )
        # Should still work, treating input as empty
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["decision"] == "block"

    def test_output_includes_task_params(self, tmp_path):
        """Stop output includes run_in_background and bypassPermissions instructions."""
        self._init_config(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        assert "run_in_background" in output["reason"]
        assert "bypassPermissions" in output["reason"]

    def test_no_output_when_config_absent(self, tmp_path):
        """Stop hook produces no output when config.json is absent (#17).

        Even if dirty-files somehow exists, an uninitialized project
        (no config.json) must not trigger the memory-updater agent.
        """
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""


class TestPreToolUseHook:
    """Tests for trigger.py PreToolUse hook behavior."""

    def _make_pre_tool_input(self, command: str) -> str:
        """Create JSON input simulating PreToolUse for a Bash command."""
        return json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_input": {"command": command},
            }
        )

    def _setup_gitmode(self, tmp_path):
        """Set up gitmode configuration."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"triggerMode": "gitmode"}))

    def test_passthrough_in_default_mode(self, tmp_path):
        """PreToolUse passes through in default trigger mode."""
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=self._make_pre_tool_input("git commit -m 'test'"),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_passthrough_non_git_commit_in_gitmode(self, tmp_path):
        """PreToolUse passes through for non-git-commit commands in gitmode."""
        self._setup_gitmode(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=self._make_pre_tool_input("git status"),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_denies_git_commit_with_dirty_files_in_gitmode(self, tmp_path):
        """PreToolUse denies git commit in gitmode when dirty files exist."""
        self._setup_gitmode(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=self._make_pre_tool_input("git commit -m 'test'"),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        hook_output = output["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "deny"
        assert "memory-updater" in hook_output["permissionDecisionReason"]

    def test_passthrough_git_commit_no_dirty_files_in_gitmode(self, tmp_path):
        """PreToolUse passes through git commit in gitmode when no dirty files."""
        self._setup_gitmode(tmp_path)

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=self._make_pre_tool_input("git commit -m 'test'"),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_deny_output_includes_task_params(self, tmp_path):
        """PreToolUse deny output includes run_in_background and bypassPermissions."""
        self._setup_gitmode(tmp_path)
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=self._make_pre_tool_input("git commit -m 'test'"),
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "run_in_background" in reason
        assert "bypassPermissions" in reason

    def test_no_output_when_config_absent(self, tmp_path):
        """PreToolUse produces no output when config.json is absent (#17).

        An uninitialized project must not have git commits intercepted.
        """
        dirty_file = tmp_path / ".claude" / "auto-memory" / "dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=self._make_pre_tool_input("git commit -m 'test'"),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""


class TestSubagentStopHook:
    """Tests for trigger.py SubagentStop hook behavior."""

    def test_clears_dirty_files_with_config(self, tmp_path):
        """Clears dirty-files when config.json and dirty-files both present."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty_file = config_dir / "dirty-files"
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=json.dumps({"hook_event_name": "SubagentStop"}),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""
        assert dirty_file.read_text() == ""

    def test_clears_dirty_files_even_without_config(self, tmp_path):
        """Still clears dirty-files when config.json is missing (#17, #25).

        Regression gate for the early-return guard that caused infinite
        Stop-hook loops on uninitialized projects.
        """
        dirty_dir = tmp_path / ".claude" / "auto-memory"
        dirty_dir.mkdir(parents=True)
        dirty_file = dirty_dir / "dirty-files"
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=json.dumps({"hook_event_name": "SubagentStop"}),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""
        assert dirty_file.read_text() == ""

    def test_noop_when_dirty_files_empty(self, tmp_path):
        """Does nothing when dirty-files is empty."""
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "default"}))
        dirty_file = config_dir / "dirty-files"
        dirty_file.write_text("")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "trigger.py"],
            env={**os.environ, **env},
            input=json.dumps({"hook_event_name": "SubagentStop"}),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""
        assert dirty_file.read_text() == ""


class TestGitCommitContext:
    """Tests for git commit context enrichment."""

    def _make_bash_input(self, command: str) -> str:
        """Create JSON input for Bash tool."""
        return json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": command},
            }
        )

    def _init_git_repo(self, tmp_path):
        """Initialize a git repo with an initial commit.

        Creates an initial commit so subsequent commits have a parent
        for git diff-tree to compare against.
        """
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
        # Create initial commit so later commits have a parent
        init_file = tmp_path / ".gitkeep"
        init_file.write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

    def test_handle_git_commit_non_git_directory(self, tmp_path):
        """handle_git_commit returns empty when not a git repo."""
        # Import the function directly
        sys.path.insert(0, str(SCRIPTS_DIR))
        from importlib import import_module

        post_tool_use = import_module("post-tool-use")

        files, context = post_tool_use.handle_git_commit(str(tmp_path))

        assert files == []
        assert context is None

        # Cleanup
        sys.path.pop(0)
        sys.modules.pop("post-tool-use", None)

    def test_handle_git_commit_extracts_files_and_context(self, tmp_path):
        """handle_git_commit extracts files and commit context from git."""
        # Initialize git repo
        self._init_git_repo(tmp_path)

        # Create and commit a file
        test_file = tmp_path / "feature.py"
        test_file.write_text("print('hello')")
        subprocess.run(["git", "add", "feature.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add feature"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Import the function directly
        sys.path.insert(0, str(SCRIPTS_DIR))
        from importlib import import_module

        post_tool_use = import_module("post-tool-use")

        files, context = post_tool_use.handle_git_commit(str(tmp_path))

        # Verify files list contains our file
        assert len(files) == 1
        assert "feature.py" in files[0]

        # Verify context has hash and message
        assert context is not None
        assert "hash" in context
        assert len(context["hash"]) == 7  # Short hash
        assert context["message"] == "Add feature"

        # Cleanup
        sys.path.pop(0)
        sys.modules.pop("post-tool-use", None)

    def test_commit_enriches_dirty_files_with_context(self, tmp_path):
        """Git commit command enriches dirty files with inline context in gitmode."""
        # Initialize git repo
        self._init_git_repo(tmp_path)

        # Set up gitmode config (commit enrichment only applies in gitmode)
        config_dir = tmp_path / ".claude" / "auto-memory"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps({"triggerMode": "gitmode"}))

        # Create and commit a file
        test_file = tmp_path / "module.py"
        test_file.write_text("# module")
        subprocess.run(["git", "add", "module.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add module"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Run hook with git commit command
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("git commit -m 'Add module'"),
            capture_output=True,
            text=True,
        )

        # Check dirty files contain commit context
        dirty_file = config_dir / "dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()

        # Should have file path with inline commit context
        assert "module.py" in content
        assert "[" in content  # Context marker
        assert ":" in content  # hash: message separator
        assert "Add module" in content
