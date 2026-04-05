"""
Integration tests for PyPI package distribution.
Tests the complete packaging workflow including version consistency.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict

import pytest


class TestPackageDistributionReadiness:
    """Tests for PyPI distribution readiness."""

    @staticmethod
    def get_pyproject_dict() -> Dict:
        """Parse pyproject.toml and return as dict."""
        import tomllib

        pyproject_file = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_file, "rb") as f:
            return tomllib.load(f)

    def test_version_consistency_across_files(self):
        """Verify version is consistent across all files."""
        import agentic_brain

        pyproject = self.get_pyproject_dict()
        pyproject_version = pyproject["project"]["version"]

        assert (
            agentic_brain.__version__ == pyproject_version
        ), f"Version mismatch: __init__.py={agentic_brain.__version__}, pyproject.toml={pyproject_version}"

    def test_package_metadata_complete(self):
        """Verify all required metadata is complete."""
        pyproject = self.get_pyproject_dict()
        project = pyproject["project"]

        required_fields = {
            "name": "Package name",
            "version": "Version",
            "description": "Description",
            "readme": "README file",
            "requires-python": "Python version requirement",
            "license": "License",
            "authors": "Authors list",
        }

        for field, description in required_fields.items():
            assert field in project, f"Missing required field: {field} ({description})"
            assert project[field], f"Empty field: {field}"

    def test_urls_configuration(self):
        """Verify all project URLs are properly configured."""
        pyproject = self.get_pyproject_dict()
        urls = pyproject["project"].get("urls", {})

        required_urls = ["Homepage", "Repository", "Documentation"]
        for url_name in required_urls:
            assert url_name in urls, f"Missing URL: {url_name}"
            assert urls[url_name].startswith(
                "https://"
            ), f"URL must be HTTPS: {url_name}"

    def test_classifiers_present(self):
        """Verify important classifiers are set."""
        pyproject = self.get_pyproject_dict()
        classifiers = pyproject["project"].get("classifiers", [])

        classifier_checks = {
            "Production/Stable": lambda c: "Development Status :: 5" in c,
            "Python 3.11+": lambda c: "Programming Language :: Python :: 3" in c,
            "Type Hints": lambda c: "Typing :: Typed" in c,
            "Framework": lambda c: "Framework" in c or "Topic" in c,
        }

        for check_name, check_fn in classifier_checks.items():
            assert any(
                check_fn(c) for c in classifiers
            ), f"Missing classifier: {check_name}"

    def test_entry_points_defined(self):
        """Verify CLI entry points are defined."""
        pyproject = self.get_pyproject_dict()
        scripts = pyproject["project"].get("scripts", {})

        required_scripts = ["agentic-brain", "agentic", "ab"]
        for script_name in required_scripts:
            assert script_name in scripts, f"Missing script: {script_name}"
            assert "agentic_brain.cli:main" == scripts[script_name]

    def test_dependencies_structure(self):
        """Verify dependencies are properly structured."""
        pyproject = self.get_pyproject_dict()
        project = pyproject["project"]

        # Check base dependencies exist
        dependencies = project.get("dependencies", [])
        assert len(dependencies) > 0, "No base dependencies defined"

        # Check each is a valid version spec
        for dep in dependencies:
            assert any(spec in dep for spec in [">=", "==", ">", "<", "~=", "|"]) or (
                "[" in dep
            ), f"Invalid dependency spec: {dep}"

    def test_optional_dependencies_defined(self):
        """Verify optional dependencies groups exist."""
        pyproject = self.get_pyproject_dict()
        opt_deps = pyproject["project"].get("optional-dependencies", {})

        required_groups = ["dev", "test", "api", "docs"]
        for group in required_groups:
            assert group in opt_deps, f"Missing optional dependency group: {group}"
            assert isinstance(
                opt_deps[group], list
            ), f"Dependency group must be a list: {group}"
            assert len(opt_deps[group]) > 0, f"Empty dependency group: {group}"

    def test_build_system_configured(self):
        """Verify build system is properly configured."""
        pyproject = self.get_pyproject_dict()
        build_system = pyproject.get("build-system", {})

        assert "requires" in build_system, "Missing build requires"
        requires = build_system.get("requires", [])
        assert any(
            "setuptools" in req for req in requires
        ), "setuptools required for build"
        assert "build-backend" in build_system, "Missing build-backend"
        assert (
            build_system["build-backend"] == "setuptools.build_meta"
        ), "Invalid build backend"

    def test_readme_file_referenced(self):
        """Verify README is referenced and contains content."""
        pyproject = self.get_pyproject_dict()
        readme_ref = pyproject["project"].get("readme")

        assert readme_ref, "No README configured"

        # Handle both string and dict formats
        if isinstance(readme_ref, str):
            readme_path = readme_ref
        elif isinstance(readme_ref, dict):
            readme_path = readme_ref.get("file")
        else:
            pytest.fail(f"Invalid readme format: {readme_ref}")

        project_dir = Path(__file__).parent.parent
        readme_file = project_dir / readme_path
        assert readme_file.exists(), f"README file not found: {readme_path}"
        assert readme_file.stat().st_size > 500, "README file is too small or empty"

    def test_license_file_referenced(self):
        """Verify LICENSE file exists."""
        project_dir = Path(__file__).parent.parent
        license_file = project_dir / "LICENSE"

        assert license_file.exists(), "LICENSE file not found"
        assert license_file.stat().st_size > 100, "LICENSE file is too small or empty"

    @pytest.mark.integration
    def test_can_import_all_exported_symbols(self):
        """Verify all exported symbols can be imported (lazy loading check)."""
        import agentic_brain

        # Test a sampling of lazy-loaded exports
        test_exports = [
            "Agent",
            "Neo4jMemory",
            "AgenticBrainError",
            "MEDICAL_DISCLAIMER",
            "ModelCard",
            "AuditLog",
        ]

        for export_name in test_exports:
            try:
                obj = getattr(agentic_brain, export_name)
                assert obj is not None, f"Lazy export {export_name} returned None"
            except AttributeError as e:
                pytest.fail(f"Cannot import lazy export: {export_name} - {e}")


@pytest.mark.integration
class TestPackageDistributionWorkflow:
    """Test the complete distribution workflow."""

    def test_publish_script_is_executable(self):
        """Verify publish script is executable."""
        script = Path(__file__).parent.parent / "scripts" / "publish.sh"
        assert script.exists(), "publish.sh not found"

        # Check execute permissions
        import stat

        mode = script.stat().st_mode
        is_executable = bool(mode & stat.S_IXUSR)
        assert is_executable, "publish.sh is not executable"

    def test_publish_script_help_works(self):
        """Verify publish script help text works."""
        script = Path(__file__).parent.parent / "scripts" / "publish.sh"

        # Just verify the file contains help text
        content = script.read_text()
        assert "Usage:" in content or "usage:" in content
        assert "--help" in content or "-h" in content

    def test_manifest_in_is_valid(self):
        """Verify MANIFEST.in has valid syntax."""
        manifest = Path(__file__).parent.parent / "MANIFEST.in"
        content = manifest.read_text()

        # Check for common MANIFEST.in directives
        valid_directives = [
            "include",
            "exclude",
            "recursive-include",
            "prune",
            "global-include",
        ]
        has_directives = any(directive in content for directive in valid_directives)
        assert has_directives, "MANIFEST.in should contain include/exclude directives"

        # Verify no syntax errors (basic check)
        lines = [
            line.strip()
            for line in content.split("\n")
            if line.strip() and not line.startswith("#")
        ]
        for line in lines:
            parts = line.split()
            assert len(parts) >= 2, f"Invalid MANIFEST.in line: {line}"
            assert parts[0] in valid_directives, f"Unknown directive: {parts[0]}"

    def test_py_typed_marker_correct(self):
        """Verify py.typed is set up correctly for PEP 561."""
        py_typed = Path(__file__).parent.parent / "src" / "agentic_brain" / "py.typed"

        assert py_typed.exists(), "py.typed marker not found"
        # py.typed should be empty (it's just a marker file)
        content = py_typed.read_text()
        assert content == "" or content.isspace(), "py.typed should be empty"


@pytest.mark.integration
class TestPackageFileStructure:
    """Test that package file structure is correct for distribution."""

    def test_src_layout_structure(self):
        """Verify package uses src/ layout (best practice)."""
        src_dir = Path(__file__).parent.parent / "src"
        agentic_brain_dir = src_dir / "agentic_brain"

        assert (
            src_dir.exists()
        ), "src/ directory not found - package should use src layout"
        assert agentic_brain_dir.exists(), "src/agentic_brain/ directory not found"
        assert (
            agentic_brain_dir / "__init__.py"
        ).exists(), "src/agentic_brain/__init__.py not found"

    def test_subpackages_have_init_files(self):
        """Verify core subpackages have __init__.py files."""
        src_dir = Path(__file__).parent.parent / "src" / "agentic_brain"

        # Check for critical subpackages
        critical_packages = [
            "exceptions",
            "legal",
            "governance",
            "router",
            "audio",
            "agent",
        ]

        for pkg_name in critical_packages:
            pkg_dir = src_dir / pkg_name
            init_file = pkg_dir / "__init__.py"

            if pkg_dir.exists():
                assert init_file.exists(), f"Missing __init__.py in {pkg_name}"

    def test_no_pycache_in_version_control(self):
        """Verify __pycache__ directories are not included."""
        project_dir = Path(__file__).parent.parent
        pycache_dirs = list(project_dir.rglob("__pycache__"))

        # Should still exist locally but should be gitignored
        gitignore = project_dir / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
            assert "__pycache__" in content, "__pycache__ not in .gitignore"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
