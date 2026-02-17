"""Tests for Community Build Sync Script."""

import tempfile
from pathlib import Path

import pytest

# Import sync module from scripts
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "community-build"))
from sync import (
    SyncReport,
    apply_branding_transform,
    collect_files,
    parse_communityignore,
    scan_for_secrets,
    should_exclude,
    should_transform,
    sync,
)


class TestParseCommunityignore:
    """Test .communityignore parsing."""

    def test_parse_valid_file(self, tmp_path):
        ignore_file = tmp_path / ".communityignore"
        ignore_file.write_text("# comment\n\nfoo/\n*.pyc\nbar.txt\n")
        patterns = parse_communityignore(ignore_file)
        assert patterns == ["foo/", "*.pyc", "bar.txt"]

    def test_parse_missing_file(self, tmp_path):
        patterns = parse_communityignore(tmp_path / "nonexistent")
        assert patterns == []

    def test_skip_comments_and_empty(self, tmp_path):
        ignore_file = tmp_path / ".communityignore"
        ignore_file.write_text("# header\n\n# another\nreal_pattern\n\n")
        patterns = parse_communityignore(ignore_file)
        assert patterns == ["real_pattern"]


class TestShouldExclude:
    """Test file exclusion logic."""

    def test_directory_pattern(self):
        assert should_exclude("docs/plans/file.md", ["docs/plans/"]) is True
        assert should_exclude("docs/other/file.md", ["docs/plans/"]) is False

    def test_exact_match(self):
        assert should_exclude("MASTER_CONTEXT.md", ["MASTER_CONTEXT.md"]) is True
        assert should_exclude("README.md", ["MASTER_CONTEXT.md"]) is False

    def test_glob_pattern(self):
        assert should_exclude("module.pyc", ["*.pyc"]) is True
        assert should_exclude("module.py", ["*.pyc"]) is False

    def test_nested_directory(self):
        assert should_exclude("__pycache__/module.cpython-311.pyc", ["__pycache__/"]) is True

    def test_no_patterns(self):
        assert should_exclude("any/file.txt", []) is False

    def test_component_match(self):
        """Pattern matching against directory components."""
        assert should_exclude("deep/__pycache__/file.pyc", ["__pycache__/"]) is True


class TestScanForSecrets:
    """Test secret detection."""

    def test_no_secrets(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("x = 1\nprint('hello')\n")
        assert scan_for_secrets(f, "clean.py") == []

    def test_detects_private_key(self, tmp_path):
        f = tmp_path / "bad.pem"
        f.write_text("-----BEGIN PRIVATE KEY-----\ndata\n-----END PRIVATE KEY-----\n")
        warnings = scan_for_secrets(f, "bad.pem")
        assert len(warnings) > 0

    def test_allowlisted_file_skipped(self, tmp_path):
        f = tmp_path / "env.example"
        f.write_text('password = "super_secret_value"\n')
        assert scan_for_secrets(f, "env.example") == []

    def test_detects_api_key_pattern(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('api_key = "AKIAIOSFODNN7EXAMPLE12345"\n')
        warnings = scan_for_secrets(f, "config.py")
        assert len(warnings) > 0


class TestSync:
    """Test full sync operation."""

    @pytest.fixture
    def source_tree(self, tmp_path):
        """Create a mock source tree."""
        src = tmp_path / "source"
        src.mkdir()

        # Create .communityignore
        (src / ".communityignore").write_text("secret/\n*.log\nINTERNAL.md\n.communityignore\n")

        # Create files that should be copied
        (src / "README.md").write_text("# Public Readme")
        (src / "core").mkdir()
        (src / "core" / "auth.py").write_text("class AuthManager: pass")

        # Create files that should be excluded
        (src / "secret").mkdir()
        (src / "secret" / "keys.json").write_text('{"key": "value"}')
        (src / "INTERNAL.md").write_text("Internal docs")
        (src / "app.log").write_text("log data")

        return src

    def test_dry_run(self, source_tree, tmp_path):
        output = tmp_path / "output"
        report = sync(source_tree, output, dry_run=True)

        assert report.total_copied > 0
        assert report.total_excluded > 0
        assert not output.exists()  # Nothing should be created

    def test_actual_sync(self, source_tree, tmp_path):
        output = tmp_path / "output"
        report = sync(source_tree, output)

        assert (output / "README.md").exists()
        assert (output / "core" / "auth.py").exists()
        assert not (output / "secret").exists()
        assert not (output / "INTERNAL.md").exists()
        assert not (output / "app.log").exists()

    def test_communityignore_excluded(self, source_tree, tmp_path):
        output = tmp_path / "output"
        report = sync(source_tree, output)

        # .communityignore itself should be excluded
        assert not (output / ".communityignore").exists()
        assert ".communityignore" in report.excluded


class TestSyncReport:
    """Test report generation."""

    def test_summary_format(self):
        report = SyncReport(
            copied=["a.py", "b.py"],
            excluded=["c.log"],
            source_dir="/src",
            output_dir="/out",
            timestamp="2026-02-17 12:00:00 UTC",
        )
        summary = report.summary()
        assert "Files copied: **2**" in summary
        assert "Files excluded: **1**" in summary

    def test_summary_with_warnings(self):
        report = SyncReport(
            copied=["a.py"],
            excluded=[],
            secret_warnings=["file.py: found secret"],
            source_dir="/src",
            output_dir="/out",
            timestamp="now",
        )
        summary = report.summary()
        assert "Secret Warnings" in summary

    def test_summary_has_review_checklist(self):
        report = SyncReport(
            copied=["a.py"],
            excluded=[],
            source_dir="/src",
            output_dir="/out",
            timestamp="now",
        )
        summary = report.summary()
        assert "Pre-Publish Review Checklist" in summary
        assert "APPROVED FOR PUBLISH" in summary


class TestBrandingTransform:
    """Test branding transform (B.3)."""

    def test_replaces_package_name(self):
        content = 'name = "coolify-mcp-hub"'
        transformed, changed = apply_branding_transform(content)
        assert changed is True
        assert 'name = "mcphub"' in transformed

    def test_replaces_display_name(self):
        content = "Welcome to Coolify MCP Hub"
        transformed, changed = apply_branding_transform(content)
        assert "MCP Hub" in transformed
        assert "Coolify" not in transformed

    def test_replaces_urls(self):
        content = "Homepage: https://airano.ir"
        transformed, changed = apply_branding_transform(content)
        assert "mcphub.dev" in transformed
        assert "airano.ir" not in transformed

    def test_replaces_repo_urls(self):
        content = "https://gitea.airano.ir/dev/coolify-mcp-hub"
        transformed, changed = apply_branding_transform(content)
        assert "github.com/airano-ir/mcphub" in transformed

    def test_replaces_email(self):
        content = "Contact: gitea@airano.ir"
        transformed, changed = apply_branding_transform(content)
        assert "hello@mcphub.dev" in transformed

    def test_strips_private_comments(self):
        content = "line1\n# PRIVATE: internal note\nline3\n"
        transformed, changed = apply_branding_transform(content)
        assert "PRIVATE" not in transformed
        assert "line1" in transformed
        assert "line3" in transformed

    def test_no_changes_returns_false(self):
        content = "clean content with no markers\n"
        transformed, changed = apply_branding_transform(content)
        assert changed is False

    def test_should_transform_pyproject(self):
        assert should_transform("pyproject.toml") is True

    def test_should_transform_readme(self):
        assert should_transform("README.md") is True

    def test_should_transform_docs(self):
        assert should_transform("docs/OAUTH_GUIDE.md") is True

    def test_should_transform_python(self):
        assert should_transform("core/auth.py") is True
        assert should_transform("server.py") is True
        assert should_transform("plugins/wordpress/plugin.py") is True

    def test_should_not_transform_binary(self):
        assert should_transform("core/data.bin") is False
        assert should_transform("images/logo.png") is False

    def test_transform_applied_in_sync(self, tmp_path):
        """Full sync should apply transforms to matching files."""
        src = tmp_path / "source"
        src.mkdir()
        (src / ".communityignore").write_text(".communityignore\n")
        (src / "README.md").write_text("Welcome to Coolify MCP Hub\nhttps://airano.ir\n")
        (src / "core").mkdir()
        (src / "core" / "auth.py").write_text("# coolify-mcp-hub internal")

        output = tmp_path / "output"
        report = sync(src, output)

        # README.md should be transformed
        readme = (output / "README.md").read_text()
        assert "MCP Hub" in readme
        assert "Coolify" not in readme
        assert "mcphub.dev" in readme
        assert "README.md" in report.transformed

        # auth.py SHOULD be transformed (Python files now in TRANSFORM_GLOBS)
        auth = (output / "core" / "auth.py").read_text()
        assert "mcphub" in auth  # transformed
