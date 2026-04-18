"""Tests for skill definitions."""

import re
from pathlib import Path

import pytest
import yaml

SKILLS_DIR = Path(__file__).parent.parent / "skills"


def parse_skill_frontmatter(skill_path: Path) -> dict:
    """Parse YAML frontmatter from a skill file."""
    content = skill_path.read_text()
    if not content.startswith("---"):
        return {}

    # Find the closing ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}

    yaml_content = content[3:end_idx].strip()
    return yaml.safe_load(yaml_content) or {}


class TestMemoryProcessorSkill:
    """Tests for memory-processor skill."""

    @pytest.fixture
    def skill_path(self):
        return SKILLS_DIR / "memory-processor" / "SKILL.md"

    def test_yaml_valid(self, skill_path):
        """Skill has valid YAML frontmatter."""
        frontmatter = parse_skill_frontmatter(skill_path)
        assert frontmatter is not None
        assert isinstance(frontmatter, dict)

    def test_has_name(self, skill_path):
        """Skill has a name field."""
        frontmatter = parse_skill_frontmatter(skill_path)
        assert "name" in frontmatter
        assert frontmatter["name"] == "memory-processor"

    def test_has_description(self, skill_path):
        """Skill has a description field."""
        frontmatter = parse_skill_frontmatter(skill_path)
        assert "description" in frontmatter
        assert len(frontmatter["description"]) > 0

    def test_has_algorithm(self, skill_path):
        """Skill contains algorithm section."""
        content = skill_path.read_text()
        assert "## Algorithm" in content

    def test_has_marker_syntax(self, skill_path):
        """Skill documents marker syntax."""
        content = skill_path.read_text()
        assert "AUTO-MANAGED" in content
        assert "END AUTO-MANAGED" in content

    def test_has_section_names(self, skill_path):
        """Skill lists section names."""
        content = skill_path.read_text()
        assert "project-description" in content
        assert "build-commands" in content
        assert "architecture" in content


class TestCodebaseAnalyzerSkill:
    """Tests for codebase-analyzer skill."""

    @pytest.fixture
    def skill_path(self):
        return SKILLS_DIR / "codebase-analyzer" / "SKILL.md"

    @pytest.fixture
    def templates_dir(self):
        return SKILLS_DIR / "codebase-analyzer" / "templates"

    def test_yaml_valid(self, skill_path):
        """Skill has valid YAML frontmatter."""
        frontmatter = parse_skill_frontmatter(skill_path)
        assert frontmatter is not None
        assert isinstance(frontmatter, dict)

    def test_has_name(self, skill_path):
        """Skill has a name field."""
        frontmatter = parse_skill_frontmatter(skill_path)
        assert "name" in frontmatter
        assert frontmatter["name"] == "codebase-analyzer"

    def test_has_description(self, skill_path):
        """Skill has a description field."""
        frontmatter = parse_skill_frontmatter(skill_path)
        assert "description" in frontmatter
        assert len(frontmatter["description"]) > 0

    def test_has_algorithm(self, skill_path):
        """Skill contains algorithm section."""
        content = skill_path.read_text()
        assert "## Algorithm" in content or "### 1." in content

    def test_references_templates(self, skill_path):
        """Skill references template files."""
        content = skill_path.read_text()
        assert "template" in content.lower()

    def test_templates_exist(self, templates_dir):
        """Template files exist."""
        assert (templates_dir / "CLAUDE.root.md.template").exists()
        assert (templates_dir / "CLAUDE.subtree.md.template").exists()


class TestTemplates:
    """Tests for CLAUDE.md templates."""

    @pytest.fixture
    def root_template(self):
        return SKILLS_DIR / "codebase-analyzer" / "templates" / "CLAUDE.root.md.template"

    @pytest.fixture
    def subtree_template(self):
        return SKILLS_DIR / "codebase-analyzer" / "templates" / "CLAUDE.subtree.md.template"

    def test_root_has_markers(self, root_template):
        """Root template has AUTO-MANAGED markers."""
        content = root_template.read_text()
        assert "<!-- AUTO-MANAGED:" in content
        assert "<!-- END AUTO-MANAGED -->" in content

    def test_root_has_manual_section(self, root_template):
        """Root template has MANUAL section."""
        content = root_template.read_text()
        assert "<!-- MANUAL -->" in content
        assert "<!-- END MANUAL -->" in content

    def test_root_has_placeholders(self, root_template):
        """Root template has placeholder variables."""
        content = root_template.read_text()
        placeholders = re.findall(r"\{\{(\w+)\}\}", content)
        assert len(placeholders) > 0
        assert "DESCRIPTION" in placeholders
        assert "BUILD_COMMANDS" in placeholders

    def test_root_token_budget(self, root_template):
        """Root template stays within token budget (150-200 lines)."""
        content = root_template.read_text()
        lines = content.split("\n")
        # Template should be under 100 lines (content expands when filled)
        assert len(lines) < 100

    def test_subtree_has_markers(self, subtree_template):
        """Subtree template has AUTO-MANAGED markers."""
        content = subtree_template.read_text()
        assert "<!-- AUTO-MANAGED:" in content
        assert "<!-- END AUTO-MANAGED -->" in content

    def test_subtree_has_module_name(self, subtree_template):
        """Subtree template has MODULE_NAME placeholder."""
        content = subtree_template.read_text()
        assert "{{MODULE_NAME}}" in content

    def test_subtree_token_budget(self, subtree_template):
        """Subtree template stays within token budget (50-75 lines)."""
        content = subtree_template.read_text()
        lines = content.split("\n")
        # Template should be under 50 lines
        assert len(lines) < 50


class TestAgentsMdTemplates:
    """Tests for AGENTS.md templates (#14 - AGENTS.md support)."""

    @pytest.fixture
    def templates_dir(self):
        return SKILLS_DIR / "codebase-analyzer" / "templates"

    @pytest.fixture
    def agents_root(self, templates_dir):
        return templates_dir / "AGENTS.root.md.template"

    @pytest.fixture
    def agents_subtree(self, templates_dir):
        return templates_dir / "AGENTS.subtree.md.template"

    @pytest.fixture
    def claude_redirect(self, templates_dir):
        return templates_dir / "CLAUDE.redirect.md.template"

    def test_agents_root_template_exists(self, agents_root):
        """AGENTS.root.md.template exists."""
        assert agents_root.exists()

    def test_agents_subtree_template_exists(self, agents_subtree):
        """AGENTS.subtree.md.template exists."""
        assert agents_subtree.exists()

    def test_claude_redirect_template_exists(self, claude_redirect):
        """CLAUDE.redirect.md.template exists."""
        assert claude_redirect.exists()

    def test_agents_root_has_markers(self, agents_root):
        """AGENTS root template has AUTO-MANAGED markers."""
        content = agents_root.read_text()
        assert "<!-- AUTO-MANAGED:" in content
        assert "<!-- END AUTO-MANAGED -->" in content

    def test_agents_root_has_manual_section(self, agents_root):
        """AGENTS root template has MANUAL section."""
        content = agents_root.read_text()
        assert "<!-- MANUAL -->" in content
        assert "<!-- END MANUAL -->" in content

    def test_agents_root_has_placeholders(self, agents_root):
        """AGENTS root template has {{PLACEHOLDER}} tokens."""
        content = agents_root.read_text()
        placeholders = re.findall(r"\{\{(\w+)\}\}", content)
        assert "DESCRIPTION" in placeholders
        assert "BUILD_COMMANDS" in placeholders

    def test_agents_subtree_has_markers(self, agents_subtree):
        """AGENTS subtree template has AUTO-MANAGED markers."""
        content = agents_subtree.read_text()
        assert "<!-- AUTO-MANAGED:" in content
        assert "<!-- END AUTO-MANAGED -->" in content

    def test_claude_redirect_has_redirect_text(self, claude_redirect):
        """CLAUDE.redirect template contains the AGENTS.md redirect instruction."""
        content = claude_redirect.read_text()
        assert "Read AGENTS.md" in content

    def test_claude_redirect_does_not_have_auto_managed_markers(self, claude_redirect):
        """CLAUDE.redirect template is static - no AUTO-MANAGED markers."""
        content = claude_redirect.read_text()
        assert "<!-- AUTO-MANAGED:" not in content
