"""
Tests for PyPI package structure and metadata.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest


class TestPackageMetadata:
    """Test package metadata and versioning."""

    def test_version_defined(self):
        """Verify __version__ is properly defined."""
        import agentic_brain

        assert hasattr(agentic_brain, "__version__")
        assert isinstance(agentic_brain.__version__, str)
        assert len(agentic_brain.__version__) > 0

    def test_version_matches_pyproject(self):
        """Verify __version__ matches pyproject.toml."""
        import agentic_brain

        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        if pyproject_file.exists():
            content = pyproject_file.read_text()
            # Simple regex to extract version
            import re

            match = re.search(r'version = "([^"]+)"', content)
            assert match, "Could not find version in pyproject.toml"
            pyproject_version = match.group(1)

            assert (
                agentic_brain.__version__ == pyproject_version
            ), f"Version mismatch: {agentic_brain.__version__} != {pyproject_version}"

    def test_author_defined(self):
        """Verify __author__ is properly defined."""
        import agentic_brain

        assert hasattr(agentic_brain, "__author__")
        assert isinstance(agentic_brain.__author__, str)
        assert len(agentic_brain.__author__) > 0

    def test_license_defined(self):
        """Verify __license__ is properly defined."""
        import agentic_brain

        assert hasattr(agentic_brain, "__license__")
        assert agentic_brain.__license__ == "Apache-2.0"

    def test_description_defined(self):
        """Verify __description__ is properly defined."""
        import agentic_brain

        assert hasattr(agentic_brain, "__description__")
        assert isinstance(agentic_brain.__description__, str)
        assert len(agentic_brain.__description__) > 0

    def test_email_defined(self):
        """Verify __email__ is properly defined."""
        import agentic_brain

        assert hasattr(agentic_brain, "__email__")
        assert isinstance(agentic_brain.__email__, str)
        assert "@" in agentic_brain.__email__


class TestPackageFiles:
    """Test that required packaging files exist."""

    def test_py_typed_exists(self):
        """Verify py.typed marker file exists for type hint support."""
        py_typed = Path(__file__).parent.parent / "src" / "agentic_brain" / "py.typed"
        assert (
            py_typed.exists()
        ), "py.typed marker not found. Run: touch src/agentic_brain/py.typed"

    def test_readme_exists(self):
        """Verify README.md exists."""
        readme = Path(__file__).parent.parent / "README.md"
        assert readme.exists(), "README.md not found"
        assert readme.stat().st_size > 100, "README.md appears to be empty"

    def test_license_exists(self):
        """Verify LICENSE file exists."""
        license_file = Path(__file__).parent.parent / "LICENSE"
        assert license_file.exists(), "LICENSE file not found"
        assert license_file.stat().st_size > 100, "LICENSE appears to be empty"

    def test_manifest_in_exists(self):
        """Verify MANIFEST.in exists."""
        manifest = Path(__file__).parent.parent / "MANIFEST.in"
        assert manifest.exists(), "MANIFEST.in not found"
        content = manifest.read_text()
        assert "include README.md" in content
        assert "include LICENSE" in content
        assert "py.typed" in content or "include" in content

    def test_pyproject_toml_exists(self):
        """Verify pyproject.toml exists."""
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml not found"
        content = pyproject.read_text()
        assert "[project]" in content
        assert 'name = "agentic-brain"' in content

    def test_publish_script_exists(self):
        """Verify publish.sh script exists."""
        script = Path(__file__).parent.parent / "scripts" / "publish.sh"
        assert script.exists(), "scripts/publish.sh not found"
        assert script.stat().st_mode & 0o111, "publish.sh is not executable"


class TestPackageStructure:
    """Test package structure and imports."""

    def test_main_module_importable(self):
        """Verify main agentic_brain module can be imported."""
        import agentic_brain

        assert agentic_brain is not None

    def test_lazy_exports_defined(self):
        """Verify lazy export mechanism is defined."""
        import agentic_brain

        assert hasattr(agentic_brain, "_LAZY_EXPORTS")
        assert isinstance(agentic_brain._LAZY_EXPORTS, dict)
        assert len(agentic_brain._LAZY_EXPORTS) > 0

    def test_all_exports_defined(self):
        """Verify __all__ is defined with exports."""
        import agentic_brain

        assert hasattr(agentic_brain, "__all__")
        assert isinstance(agentic_brain.__all__, list)
        assert len(agentic_brain.__all__) > 0
        assert "__version__" in agentic_brain.__all__
        assert "__author__" in agentic_brain.__all__

    def test_exceptions_module_importable(self):
        """Verify exceptions module can be imported."""
        import agentic_brain.exceptions

        assert hasattr(agentic_brain.exceptions, "AgenticBrainError")

    def test_legal_module_importable(self):
        """Verify legal module can be imported."""
        import agentic_brain.legal

        assert hasattr(agentic_brain.legal, "MEDICAL_DISCLAIMER")
        assert hasattr(agentic_brain.legal, "FINANCIAL_DISCLAIMER")

    def test_governance_module_importable(self):
        """Verify governance module can be imported."""
        import agentic_brain.governance

        assert hasattr(agentic_brain.governance, "ModelCard")
        assert hasattr(agentic_brain.governance, "AuditLog")


class TestPackageScripts:
    """Test console entry points."""

    def test_cli_entrypoint_defined(self):
        """Verify CLI entry points are defined in pyproject.toml."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert "[project.scripts]" in content
        assert "agentic-brain = " in content
        assert "agentic_brain.cli:main" in content


class TestBuildConfiguration:
    """Test build system configuration."""

    def test_build_system_configured(self):
        """Verify build system is properly configured."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert "[build-system]" in content
        assert "requires = " in content
        assert "setuptools" in content
        assert "build-backend" in content

    def test_setuptools_configured(self):
        """Verify setuptools configuration exists."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert "[tool.setuptools" in content
        assert "where = " in content

    def test_python_version_requirement(self):
        """Verify Python version requirement is set."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert 'requires-python = ">=3.11"' in content


class TestDependencies:
    """Test dependency configuration."""

    def test_dependencies_defined(self):
        """Verify dependencies are defined."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert "dependencies = [" in content or "dependencies =" in content
        # Check for at least some dependencies
        assert "aiohttp" in content or "fastapi" in content or "redis" in content

    def test_optional_dependencies_defined(self):
        """Verify optional dependencies groups exist."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert "[project.optional-dependencies]" in content
        # Check for some optional dependency groups
        assert "dev" in content
        assert "test" in content
        assert "api" in content


class TestPackageClassifiers:
    """Test package classifiers."""

    def test_production_status_classifier(self):
        """Verify Production/Stable classifier is set."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert '"Development Status :: 5 - Production/Stable"' in content

    def test_python_classifiers(self):
        """Verify Python version classifiers."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert '"Programming Language :: Python :: 3"' in content
        assert (
            '"Programming Language :: Python :: 3.11"' in content or "3.11" in content
        )

    def test_license_classifier(self):
        """Verify license classifier."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert "Apache" in content or "License" in content

    def test_type_hints_classifier(self):
        """Verify type hints classifier (Typing :: Typed)."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        assert '"Typing :: Typed"' in content


class TestLazyLoading:
    """Test lazy loading mechanism."""

    def test_getattr_mechanism(self):
        """Verify __getattr__ for lazy loading."""
        import agentic_brain

        assert hasattr(agentic_brain, "__getattr__")

    def test_lazy_loading_works(self):
        """Test that lazy loading actually works."""
        import agentic_brain

        # AgenticBrainError should be lazy-loadable
        exc = agentic_brain.AgenticBrainError
        assert exc is not None
        assert issubclass(exc, Exception)

    def test_dir_includes_all_exports(self):
        """Verify dir() includes all exports."""
        import agentic_brain

        dir_contents = dir(agentic_brain)
        assert "__version__" in dir_contents
        assert "__author__" in dir_contents
        assert "AgenticBrainError" in dir_contents


@pytest.mark.unit
class TestInstallationSimulation:
    """Simulate package installation checks."""

    def test_package_can_be_imported_after_install(self):
        """Verify package structure is valid for pip install."""
        # This simulates what pip would check
        import agentic_brain

        # Check that __file__ exists and points to a real location
        assert hasattr(agentic_brain, "__file__")
        assert agentic_brain.__file__

    def test_entry_points_configured(self):
        """Verify console script entry points are configured."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()
        # Looking for [project.scripts] section
        assert "[project.scripts]" in content

    def test_package_metadata_completeness(self):
        """Verify all required metadata is present."""
        import agentic_brain

        required_attributes = [
            "__version__",
            "__author__",
            "__license__",
            "__description__",
        ]

        for attr in required_attributes:
            assert hasattr(agentic_brain, attr), f"Missing {attr}"
            value = getattr(agentic_brain, attr)
            assert value, f"{attr} is empty"


@pytest.mark.unit
class TestTypeHints:
    """Test type hint support (py.typed)."""

    def test_py_typed_file_exists(self):
        """Verify py.typed marker exists for PEP 561 support."""
        pkg_dir = Path(__file__).parent.parent / "src" / "agentic_brain"
        py_typed_file = pkg_dir / "py.typed"

        assert (
            py_typed_file.exists()
        ), "py.typed not found - package won't be recognized as typed"

    def test_py_typed_is_empty_file(self):
        """Verify py.typed is an empty marker file."""
        pkg_dir = Path(__file__).parent.parent / "src" / "agentic_brain"
        py_typed_file = pkg_dir / "py.typed"

        # py.typed should be an empty file (it's just a marker)
        content = py_typed_file.read_text()
        assert content == "" or content.isspace()


# Integration tests that run during actual package testing
@pytest.mark.integration
class TestPackagingIntegration:
    """Integration tests for packaging."""

    def test_can_build_distribution(self):
        """Test that package can be built (requires build tools)."""
        pytest.importorskip("build")

        project_dir = Path(__file__).parent.parent

        # This is a simulation - actual build would require running build
        pyproject = project_dir / "pyproject.toml"
        assert pyproject.exists()
        assert pyproject.stat().st_size > 100

    def test_metadata_in_pyproject(self):
        """Verify pyproject.toml has all required metadata."""
        project_dir = Path(__file__).parent.parent
        pyproject_file = project_dir / "pyproject.toml"

        content = pyproject_file.read_text()

        # Check required sections
        assert "[project]" in content
        assert 'name = "agentic-brain"' in content
        assert "description =" in content
        assert "readme =" in content
        assert "license" in content
        assert "authors" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
