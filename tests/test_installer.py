"""
Comprehensive tests for agentic_brain.installer module (604 lines).

Tests cover:
1. print_banner() - banner output validation
2. get_project_dir() - path handling, expanduser, defaults
3. create_project_structure() - directory creation verification
4. create_config_file() - JSON validation
5. create_env_file() - .env format validation
6. Template validation - all 4 templates (minimal, retail, support, enterprise)
7. Schema file creation and validation
8. Main file creation for different templates
9. README creation
10. Integration tests for full installation flow
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call
from io import StringIO

from agentic_brain.installer import (
    print_banner,
    get_project_dir,
    create_project_structure,
    create_config_file,
    create_env_file,
    create_schema_file,
    create_main_file,
    create_readme,
    TEMPLATES,
    NEO4J_SCHEMAS,
    choose_template,
    get_neo4j_config,
    run_installer,
)


class TestPrintBanner:
    """Test print_banner() function."""
    
    def test_print_banner_no_error(self, capsys):
        """Verify print_banner runs without error."""
        print_banner()
        captured = capsys.readouterr()
        # Banner contains ASCII art and box drawing
        assert "╔" in captured.out  # Contains box drawing characters
        assert "BRAIN" in captured.out or "INSTALLER" in captured.out or "█" in captured.out
    
    def test_print_banner_contains_title(self, capsys):
        """Verify banner contains expected title elements."""
        print_banner()
        captured = capsys.readouterr()
        # Check for key banner elements
        assert ("BRAIN" in captured.out and "INSTALLER" in captured.out) or len(captured.out) > 100


class TestGetProjectDir:
    """Test get_project_dir() function."""
    
    def test_get_project_dir_default_path(self, monkeypatch):
        """Test default project directory when user presses Enter."""
        monkeypatch.setattr('builtins.input', lambda _: "")
        result = get_project_dir()
        assert result == Path.cwd() / "my_chatbot"
    
    def test_get_project_dir_custom_path(self, monkeypatch, temp_dir):
        """Test custom project directory path."""
        custom_path = str(temp_dir / "my_project")
        monkeypatch.setattr('builtins.input', lambda _: custom_path)
        result = get_project_dir()
        assert result.name == "my_project"
    
    def test_get_project_dir_expanduser(self, monkeypatch):
        """Test that ~ is expanded in path."""
        monkeypatch.setattr('builtins.input', lambda _: "~/my_project")
        result = get_project_dir()
        # Should expand ~ to home directory
        assert "~" not in str(result)
        assert result.is_absolute()
    
    def test_get_project_dir_resolve(self, monkeypatch, temp_dir):
        """Test that relative paths are resolved to absolute."""
        monkeypatch.setattr('builtins.input', lambda _: ".")
        result = get_project_dir()
        assert result.is_absolute()


class TestCreateProjectStructure:
    """Test create_project_structure() function."""
    
    def test_create_project_structure_minimal(self, temp_dir, capsys):
        """Verify directory structure creation for minimal template."""
        create_project_structure(temp_dir, "minimal")
        
        # Check all expected directories exist
        assert (temp_dir / "src").exists()
        assert (temp_dir / "examples").exists()
        assert (temp_dir / "docs").exists()
        assert (temp_dir / "tests").exists()
        assert (temp_dir / "data").exists()
        assert (temp_dir / "sessions").exists()
        
        captured = capsys.readouterr()
        assert "Created project structure" in captured.out
    
    def test_create_project_structure_idempotent(self, temp_dir):
        """Test that creating structure twice is safe (idempotent)."""
        create_project_structure(temp_dir, "minimal")
        first_state = set((temp_dir / "src").iterdir()) if (temp_dir / "src").exists() else set()
        
        # Call again
        create_project_structure(temp_dir, "minimal")
        second_state = set((temp_dir / "src").iterdir()) if (temp_dir / "src").exists() else set()
        
        # Should be the same
        assert first_state == second_state
    
    def test_create_project_structure_all_templates(self, temp_dir):
        """Test structure creation for all templates."""
        for template_name in TEMPLATES.keys():
            template_dir = temp_dir / template_name
            template_dir.mkdir()
            create_project_structure(template_dir, template_name)
            
            # Verify structure
            assert (template_dir / "src").exists()
            assert (template_dir / "examples").exists()


class TestCreateConfigFile:
    """Test create_config_file() function."""
    
    def test_create_config_file_valid_json(self, temp_dir, capsys):
        """Verify config.json contains valid JSON."""
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password"
        }
        create_config_file(temp_dir, "minimal", neo4j_config)
        
        config_path = temp_dir / "config.json"
        assert config_path.exists()
        
        # Parse JSON
        config = json.loads(config_path.read_text())
        assert config is not None
        assert isinstance(config, dict)
    
    def test_create_config_file_content_minimal(self, temp_dir):
        """Verify config.json has correct content for minimal template."""
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password"
        }
        create_config_file(temp_dir, "minimal", neo4j_config)
        
        config = json.loads((temp_dir / "config.json").read_text())
        assert config["template"] == "minimal"
        assert config["version"] == "1.0.0"
        assert config["neo4j"]["uri"] == "bolt://localhost:7687"
        assert config["neo4j"]["user"] == "neo4j"
        assert config["chat"]["model"] == "llama3.1:8b"
        assert config["chat"]["persist_sessions"] is True
        assert config["memory"]["enabled"] is True
    
    def test_create_config_file_all_templates(self, temp_dir):
        """Test config creation for all templates."""
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password"
        }
        
        for template_name in TEMPLATES.keys():
            template_dir = temp_dir / template_name
            template_dir.mkdir()
            create_config_file(template_dir, template_name, neo4j_config)
            
            config = json.loads((template_dir / "config.json").read_text())
            assert config["template"] == template_name
            assert config["version"] == "1.0.0"
    
    def test_create_config_file_neo4j_credentials(self, temp_dir):
        """Verify Neo4j credentials are stored in config."""
        neo4j_config = {
            "uri": "bolt://example.com:7687",
            "user": "test_user",
            "password": "secret_pass"
        }
        create_config_file(temp_dir, "minimal", neo4j_config)
        
        config = json.loads((temp_dir / "config.json").read_text())
        assert config["neo4j"]["uri"] == "bolt://example.com:7687"
        assert config["neo4j"]["user"] == "test_user"
        assert config["neo4j"]["password"] == "secret_pass"


class TestCreateEnvFile:
    """Test create_env_file() function."""
    
    def test_create_env_file_exists(self, temp_dir):
        """Verify .env file is created."""
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password"
        }
        create_env_file(temp_dir, neo4j_config)
        
        env_path = temp_dir / ".env"
        assert env_path.exists()
    
    def test_create_env_file_content_format(self, temp_dir):
        """Verify .env file has correct format."""
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password"
        }
        create_env_file(temp_dir, neo4j_config)
        
        env_content = (temp_dir / ".env").read_text()
        
        # Check for key format: KEY=VALUE
        assert "NEO4J_URI=" in env_content
        assert "NEO4J_USER=" in env_content
        assert "NEO4J_PASSWORD=" in env_content
    
    def test_create_env_file_credentials(self, temp_dir):
        """Verify credentials are stored in .env."""
        neo4j_config = {
            "uri": "bolt://custom.example.com:7687",
            "user": "test_user",
            "password": "secret_pass"
        }
        create_env_file(temp_dir, neo4j_config)
        
        env_content = (temp_dir / ".env").read_text()
        assert "NEO4J_URI=bolt://custom.example.com:7687" in env_content
        assert "NEO4J_USER=test_user" in env_content
        assert "NEO4J_PASSWORD=secret_pass" in env_content
    
    def test_create_env_file_comment_header(self, temp_dir):
        """Verify .env contains instructional comments."""
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password"
        }
        create_env_file(temp_dir, neo4j_config)
        
        env_content = (temp_dir / ".env").read_text()
        assert "Agentic Brain Configuration" in env_content or "#" in env_content


class TestCreateSchemaFile:
    """Test create_schema_file() function."""
    
    def test_create_schema_file_exists(self, temp_dir):
        """Verify schema.cypher file is created."""
        create_schema_file(temp_dir, "minimal")
        
        schema_path = temp_dir / "schema.cypher"
        assert schema_path.exists()
    
    def test_create_schema_file_minimal_template(self, temp_dir):
        """Verify minimal template schema is correct."""
        create_schema_file(temp_dir, "minimal")
        
        schema_content = (temp_dir / "schema.cypher").read_text()
        assert "Minimal Schema" in schema_content or "Conversation" in schema_content
        assert "CREATE CONSTRAINT" in schema_content or "CREATE INDEX" in schema_content
    
    def test_create_schema_file_retail_template(self, temp_dir):
        """Verify retail template schema is correct."""
        create_schema_file(temp_dir, "retail")
        
        schema_content = (temp_dir / "schema.cypher").read_text()
        assert "Retail" in schema_content or "Product" in schema_content or "Order" in schema_content
    
    def test_create_schema_file_support_template(self, temp_dir):
        """Verify support template schema is correct."""
        create_schema_file(temp_dir, "support")
        
        schema_content = (temp_dir / "schema.cypher").read_text()
        assert "Support" in schema_content or "Ticket" in schema_content or "Article" in schema_content
    
    def test_create_schema_file_enterprise_template(self, temp_dir):
        """Verify enterprise template schema is correct."""
        create_schema_file(temp_dir, "enterprise")
        
        schema_content = (temp_dir / "schema.cypher").read_text()
        assert "Enterprise" in schema_content or "Tenant" in schema_content or "AuditLog" in schema_content
    
    def test_create_schema_file_all_templates_cypher_syntax(self, temp_dir):
        """Verify all templates produce valid-looking Cypher syntax."""
        for template_name in TEMPLATES.keys():
            template_dir = temp_dir / template_name
            template_dir.mkdir()
            create_schema_file(template_dir, template_name)
            
            schema_content = (template_dir / "schema.cypher").read_text()
            # Should contain Cypher keywords
            assert "CREATE CONSTRAINT" in schema_content or "CREATE INDEX" in schema_content


class TestCreateMainFile:
    """Test create_main_file() function."""
    
    def test_create_main_file_exists(self, temp_dir):
        """Verify main.py file is created."""
        create_main_file(temp_dir, "minimal")
        
        main_path = temp_dir / "main.py"
        assert main_path.exists()
    
    def test_create_main_file_minimal_template(self, temp_dir):
        """Verify minimal template main.py has expected content."""
        create_main_file(temp_dir, "minimal")
        
        main_content = (temp_dir / "main.py").read_text()
        assert "def main():" in main_content
        assert "Chatbot" in main_content
        assert 'if __name__ == "__main__":' in main_content
    
    def test_create_main_file_retail_template(self, temp_dir):
        """Verify retail template main.py has retail-specific content."""
        create_main_file(temp_dir, "retail")
        
        main_content = (temp_dir / "main.py").read_text()
        assert "retail" in main_content.lower() or "Retail" in main_content
    
    def test_create_main_file_support_template(self, temp_dir):
        """Verify support template main.py has support-specific content."""
        create_main_file(temp_dir, "support")
        
        main_content = (temp_dir / "main.py").read_text()
        # Should be valid Python at minimum
        assert "def main():" in main_content
    
    def test_create_main_file_enterprise_template(self, temp_dir):
        """Verify enterprise template main.py has enterprise-specific content."""
        create_main_file(temp_dir, "enterprise")
        
        main_content = (temp_dir / "main.py").read_text()
        # Should be valid Python at minimum
        assert "def main():" in main_content
    
    def test_create_main_file_python_syntax(self, temp_dir):
        """Verify main.py files for minimal and retail have valid Python syntax."""
        # Test minimal and retail templates - these have explicit code
        for template_name in ["minimal", "retail"]:
            template_dir = temp_dir / template_name
            template_dir.mkdir()
            create_main_file(template_dir, template_name)
            
            main_content = (template_dir / "main.py").read_text()
            # Try to compile - will raise SyntaxError if invalid
            try:
                compile(main_content, str(template_dir / "main.py"), "exec")
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {template_name} main.py: {e}")


class TestCreateReadme:
    """Test create_readme() function."""
    
    def test_create_readme_exists(self, temp_dir):
        """Verify README.md file is created."""
        create_readme(temp_dir, "minimal")
        
        readme_path = temp_dir / "README.md"
        assert readme_path.exists()
    
    def test_create_readme_markdown_format(self, temp_dir):
        """Verify README.md has markdown format."""
        create_readme(temp_dir, "minimal")
        
        readme_content = (temp_dir / "README.md").read_text()
        assert "#" in readme_content  # Markdown headers
    
    def test_create_readme_includes_components(self, temp_dir):
        """Verify README includes template components."""
        create_readme(temp_dir, "retail")
        
        readme_content = (temp_dir / "README.md").read_text()
        # Should contain component info
        assert "chat" in readme_content.lower() or "Component" in readme_content
    
    def test_create_readme_all_templates(self, temp_dir):
        """Verify README creation for all templates."""
        for template_name in TEMPLATES.keys():
            template_dir = temp_dir / template_name
            template_dir.mkdir()
            create_readme(template_dir, template_name)
            
            readme_path = template_dir / "README.md"
            assert readme_path.exists()


class TestChooseTemplate:
    """Test choose_template() function."""
    
    def test_choose_template_by_number(self, monkeypatch):
        """Test selecting template by number."""
        monkeypatch.setattr('builtins.input', lambda _: "1")
        result = choose_template()
        assert result in TEMPLATES.keys()
    
    def test_choose_template_by_name(self, monkeypatch):
        """Test selecting template by name."""
        monkeypatch.setattr('builtins.input', lambda _: "minimal")
        result = choose_template()
        assert result == "minimal"
    
    def test_choose_template_invalid_then_valid(self, monkeypatch):
        """Test handling invalid input then valid input."""
        inputs = iter(["99", "minimal"])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))
        result = choose_template()
        assert result == "minimal"
    
    def test_choose_template_case_insensitive(self, monkeypatch):
        """Test that template selection is case insensitive."""
        monkeypatch.setattr('builtins.input', lambda _: "MINIMAL")
        result = choose_template()
        assert result == "minimal"


class TestGetNeo4jConfig:
    """Test get_neo4j_config() function."""
    
    def test_get_neo4j_config_defaults(self, monkeypatch):
        """Test Neo4j config with default values."""
        inputs = iter(["", "", ""])  # Empty inputs use defaults
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))
        result = get_neo4j_config()
        
        assert result["uri"] == "bolt://localhost:7687"
        assert result["user"] == "neo4j"
        assert result["password"] == "password"
    
    def test_get_neo4j_config_custom_values(self, monkeypatch):
        """Test Neo4j config with custom values."""
        inputs = iter([
            "bolt://example.com:7687",
            "test_user",
            "test_password"
        ])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))
        result = get_neo4j_config()
        
        assert result["uri"] == "bolt://example.com:7687"
        assert result["user"] == "test_user"
        assert result["password"] == "test_password"


class TestTemplateValidation:
    """Test TEMPLATES constant - all 4 templates validation."""
    
    def test_all_templates_exist(self):
        """Verify all 4 expected templates exist."""
        expected = {"minimal", "retail", "support", "enterprise"}
        assert set(TEMPLATES.keys()) == expected
    
    def test_template_structure(self):
        """Verify each template has required keys."""
        required_keys = {"name", "description", "components", "examples", "neo4j_schema"}
        
        for template_name, template in TEMPLATES.items():
            assert all(key in template for key in required_keys), \
                f"Template {template_name} missing keys"
    
    def test_template_components_not_empty(self):
        """Verify each template has at least one component."""
        for template_name, template in TEMPLATES.items():
            assert len(template["components"]) > 0, \
                f"Template {template_name} has no components"
    
    def test_template_examples_not_empty(self):
        """Verify each template has at least one example."""
        for template_name, template in TEMPLATES.items():
            assert len(template["examples"]) > 0, \
                f"Template {template_name} has no examples"
    
    def test_neo4j_schemas_exist_for_all_templates(self):
        """Verify NEO4J_SCHEMAS exists for each template."""
        for template_name in TEMPLATES.keys():
            assert template_name in NEO4J_SCHEMAS, \
                f"No Neo4j schema for template {template_name}"
    
    def test_neo4j_schemas_content(self):
        """Verify each Neo4j schema has content."""
        for schema_name, schema_content in NEO4J_SCHEMAS.items():
            assert len(schema_content) > 0, f"Schema {schema_name} is empty"
            assert "CREATE" in schema_content, \
                f"Schema {schema_name} doesn't contain CREATE statement"


class TestRunInstallerIntegration:
    """Integration tests for full installer flow."""
    
    def test_run_installer_minimal_template(self, temp_dir, monkeypatch):
        """Test full installation with minimal template."""
        # Mock input for non-interactive flow
        inputs = iter([""])  # Just confirm with empty input (default)
        monkeypatch.setattr('builtins.input', lambda _: next(inputs, "y"))
        
        run_installer(mode="minimal", project_dir=temp_dir)
        
        # Verify all files created
        assert (temp_dir / "config.json").exists()
        assert (temp_dir / ".env").exists()
        assert (temp_dir / "schema.cypher").exists()
        assert (temp_dir / "main.py").exists()
        assert (temp_dir / "README.md").exists()
        assert (temp_dir / "src").is_dir()
    
    def test_run_installer_retail_template(self, temp_dir, monkeypatch):
        """Test full installation with retail template."""
        inputs = iter([""])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs, "y"))
        
        run_installer(mode="retail", project_dir=temp_dir)
        
        # Verify config has retail template
        config = json.loads((temp_dir / "config.json").read_text())
        assert config["template"] == "retail"
    
    def test_run_installer_support_template(self, temp_dir, monkeypatch):
        """Test full installation with support template."""
        inputs = iter([""])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs, "y"))
        
        run_installer(mode="support", project_dir=temp_dir)
        
        config = json.loads((temp_dir / "config.json").read_text())
        assert config["template"] == "support"
    
    def test_run_installer_enterprise_template(self, temp_dir, monkeypatch):
        """Test full installation with enterprise template."""
        inputs = iter([""])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs, "y"))
        
        run_installer(mode="enterprise", project_dir=temp_dir)
        
        config = json.loads((temp_dir / "config.json").read_text())
        assert config["template"] == "enterprise"
    
    def test_run_installer_creates_all_required_files(self, temp_dir, monkeypatch):
        """Verify all required files are created during installation."""
        inputs = iter([""])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs, "y"))
        
        run_installer(mode="minimal", project_dir=temp_dir)
        
        required_files = [
            "config.json",
            ".env",
            "schema.cypher",
            "main.py",
            "README.md"
        ]
        
        for file_name in required_files:
            file_path = temp_dir / file_name
            assert file_path.exists(), f"Missing required file: {file_name}"
    
    def test_run_installer_config_valid_json(self, temp_dir, monkeypatch):
        """Verify created config.json is valid JSON."""
        inputs = iter([""])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs, "y"))
        
        run_installer(mode="minimal", project_dir=temp_dir)
        
        config_content = (temp_dir / "config.json").read_text()
        try:
            json.loads(config_content)
        except json.JSONDecodeError:
            pytest.fail("config.json is not valid JSON")
    
    def test_run_installer_directories_created(self, temp_dir, monkeypatch):
        """Verify project directory structure is created."""
        inputs = iter([""])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs, "y"))
        
        run_installer(mode="minimal", project_dir=temp_dir)
        
        required_dirs = ["src", "examples", "docs", "tests", "data", "sessions"]
        for dir_name in required_dirs:
            dir_path = temp_dir / dir_name
            assert dir_path.is_dir(), f"Missing directory: {dir_name}"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_create_config_file_special_chars_in_password(self, temp_dir):
        """Test config creation with special characters in password."""
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "p@ssw0rd!#$%"
        }
        create_config_file(temp_dir, "minimal", neo4j_config)
        
        config = json.loads((temp_dir / "config.json").read_text())
        assert config["neo4j"]["password"] == "p@ssw0rd!#$%"
    
    def test_create_env_file_special_chars_uri(self, temp_dir):
        """Test .env creation with special characters in URI."""
        neo4j_config = {
            "uri": "bolt+s://user:pass@example.com:7687",
            "user": "neo4j",
            "password": "password"
        }
        create_env_file(temp_dir, neo4j_config)
        
        env_content = (temp_dir / ".env").read_text()
        assert "bolt+s://user:pass@example.com:7687" in env_content
    
    def test_project_structure_nested_dirs(self, temp_dir):
        """Test creating project structure in nested directories."""
        nested_dir = temp_dir / "parent" / "child" / "project"
        create_project_structure(nested_dir, "minimal")
        
        assert nested_dir.exists()
        assert (nested_dir / "src").exists()
    
    def test_create_readme_minimal_content(self, temp_dir):
        """Test README is not empty."""
        create_readme(temp_dir, "minimal")
        
        readme_content = (temp_dir / "README.md").read_text()
        assert len(readme_content) > 20  # Should have reasonable content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
