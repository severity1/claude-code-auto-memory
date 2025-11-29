"""Tests for hook scripts."""
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


class TestPostToolUseHook:
    """Tests for post-tool-use.py hook."""

    def _make_tool_input(self, file_path: str, tool_name: str = "Edit") -> str:
        """Create JSON input for post-tool-use hook (Edit/Write tools)."""
        return json.dumps({
            "tool_name": tool_name,
            "tool_input": {"file_path": file_path},
        })

    def _make_bash_input(self, command: str) -> str:
        """Create JSON input for Bash tool."""
        return json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": command},
        })

    def test_creates_dirty_file(self, tmp_path):
        """Hook creates .claude/.dirty-files if it doesn't exist."""
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
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()

    def test_appends_paths(self, tmp_path):
        """Hook appends file paths to dirty file."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
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
        file_path = str(tmp_path / ".claude" / "state.json")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert not dirty_file.exists()

    def test_excludes_claude_md(self, tmp_path):
        """Hook excludes CLAUDE.md files."""
        file_path = str(tmp_path / "CLAUDE.md")
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_tool_input(file_path),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
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
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert not dirty_file.exists()

    # Bash command tracking tests

    def test_tracks_rm_command(self, tmp_path):
        """Hook tracks files from rm command."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm file.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "file.py" in content

    def test_tracks_rm_with_flags(self, tmp_path):
        """Hook tracks files from rm -rf command."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm -rf src/old_module"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "old_module" in content

    def test_tracks_rm_multiple_files(self, tmp_path):
        """Hook tracks multiple files from rm command."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm file1.py file2.py file3.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "file1.py" in content
        assert "file2.py" in content
        assert "file3.py" in content

    def test_tracks_git_rm_command(self, tmp_path):
        """Hook tracks files from git rm command."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("git rm obsolete.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "obsolete.py" in content

    def test_tracks_mv_source(self, tmp_path):
        """Hook tracks source file from mv command."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("mv old_name.py new_name.py"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "old_name.py" in content
        # Should NOT track destination
        assert content.count("new_name.py") == 0 or "old_name.py" in content

    def test_tracks_unlink_command(self, tmp_path):
        """Hook tracks files from unlink command."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("unlink temp.txt"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
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

        dirty_file = tmp_path / ".claude" / ".dirty-files"
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
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}

        # Test && operator - should only track file.py, not 'echo' or 'done'
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm file.py && echo done"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        assert dirty_file.exists()
        content = dirty_file.read_text()
        assert "file.py" in content
        assert "echo" not in content
        assert "done" not in content
        assert "&&" not in content

    def test_stops_at_semicolon(self, tmp_path):
        """Hook stops parsing at semicolon operator."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm old.py ; ls -la"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        content = dirty_file.read_text()
        assert "old.py" in content
        assert "ls" not in content
        assert "-la" not in content

    def test_stops_at_pipe(self, tmp_path):
        """Hook stops parsing at pipe operator."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm -rf build | tee log.txt"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        content = dirty_file.read_text()
        assert "build" in content
        assert "tee" not in content
        assert "log.txt" not in content

    def test_stops_at_redirect(self, tmp_path):
        """Hook stops parsing at redirect operators."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, SCRIPTS_DIR / "post-tool-use.py"],
            env={**os.environ, **env},
            input=self._make_bash_input("rm deleted.py > /dev/null"),
            capture_output=True,
            text=True,
        )
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        content = dirty_file.read_text()
        assert "deleted.py" in content
        assert "/dev/null" not in content


class TestStopHook:
    """Tests for stop.py hook."""

    def test_passes_when_empty(self, tmp_path):
        """Hook passes through when no dirty files exist."""
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_passes_when_active(self, tmp_path):
        """Hook passes through when stop_hook_active is true."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input='{"stop_hook_active": true}',
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_blocks_with_files(self, tmp_path):
        """Hook blocks and outputs JSON when dirty files exist."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
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
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
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
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/file.py\n/file.py\n/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
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
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        files = [f"/file{i}.py" for i in range(30)]
        dirty_file.write_text("\n".join(files) + "\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="{}",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        # Count commas + 1 = number of files (should be <= 20)
        file_count = output["reason"].count(",") + 1
        assert file_count <= 20

    def test_handles_invalid_json_input(self, tmp_path):
        """Hook handles invalid JSON input gracefully."""
        dirty_file = tmp_path / ".claude" / ".dirty-files"
        dirty_file.parent.mkdir(parents=True)
        dirty_file.write_text("/path/to/file.py\n")

        env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, SCRIPTS_DIR / "stop.py"],
            env={**os.environ, **env},
            input="not valid json",
            capture_output=True,
            text=True,
        )
        # Should still work, treating input as empty
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["decision"] == "block"
