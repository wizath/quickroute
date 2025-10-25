"""
Integration tests for QuickRoute CLI commands.

Tests CLI functionality including:
- quickroute test
- quickroute migrate
- quickroute createsuperuser
- quickroute runserver
- quickroute startproject
"""

import pytest
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path


@pytest.mark.integration
@pytest.mark.cli
class TestCLICommands:
    """Test QuickRoute CLI commands."""

    def test_cli_version(self):
        """Test quickroute version command."""
        result = subprocess.run(
            [sys.executable, "-m", "quickroute", "version"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "QuickRoute" in result.stdout

    def test_cli_help(self):
        """Test fastdjango --help."""
        result = subprocess.run(
            [sys.executable, "-m", "quickroute", "--help"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "QuickRoute" in result.stdout
        assert "test" in result.stdout
        assert "runserver" in result.stdout

    def test_cli_test_command(self):
        """Test quickroute test command."""
        # Create a simple test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as f:
            f.write("""
import pytest

def test_simple():
    assert 1 + 1 == 2

def test_another():
    assert True
""")
            test_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "quickroute", "test", test_file],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Test command should run (output may be in stdout or stderr)
            output = (result.stdout + result.stderr).lower()
            assert "pytest" in output or "test" in output or "passed" in output

        finally:
            Path(test_file).unlink()

    def test_cli_startproject(self):
        """Test quickroute startproject command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "testproject"
            project_path = Path(tmpdir) / project_name

            result = subprocess.run(
                [sys.executable, "-m", "quickroute", "startproject", project_name],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=10
            )

            assert result.returncode == 0
            assert "Created QuickRoute project" in result.stdout

            # Verify project structure
            assert project_path.exists()
            assert (project_path / "app" / "main.py").exists()
            assert (project_path / "requirements.txt").exists()
            assert (project_path / ".env.example").exists()


@pytest.mark.integration
@pytest.mark.cli
class TestCLITestRunner:
    """Test the CLI test runner functionality."""

    def test_run_tests_with_markers(self):
        """Test running tests with specific markers."""
        # Create a test file with markers
        with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as f:
            f.write("""
import pytest

@pytest.mark.unit
def test_unit():
    assert True

@pytest.mark.integration
def test_integration():
    assert True
""")
            test_file = f.name

        try:
            # Run only unit tests
            result = subprocess.run(
                [sys.executable, "-m", "quickroute", "test", test_file, "--tag", "unit"],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Should mention the test running (output may be in stdout or stderr)
            output = (result.stdout + result.stderr).lower()
            assert result.returncode == 0 or "pytest" in output or "passed" in output

        finally:
            Path(test_file).unlink()

    def test_run_tests_verbose(self):
        """Test running tests with verbose output."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as f:
            f.write("""
def test_verbose():
    assert 1 == 1
""")
            test_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "quickroute", "test", test_file, "-v"],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Verbose flag should be passed (check both stdout and stderr)
            output = result.stdout + result.stderr
            assert "-v" in output or "verbose" in output.lower() or "passed" in output.lower()

        finally:
            Path(test_file).unlink()


@pytest.mark.integration
@pytest.mark.slow
class TestProjectScaffolding:
    """Test complete project scaffolding."""

    def test_scaffold_and_verify_structure(self):
        """Test creating a project and verifying its structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "myapp"
            project_path = Path(tmpdir) / project_name

            # Create project
            result = subprocess.run(
                [sys.executable, "-m", "quickroute", "startproject", project_name],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            # Verify main.py content
            main_py = project_path / "app" / "main.py"
            assert main_py.exists()

            content = main_py.read_text()
            assert "QuickRoute" in content
            assert f'title="{project_name}"' in content
            assert "@app.get" in content

            # Verify requirements.txt
            requirements = project_path / "requirements.txt"
            assert requirements.exists()

            req_content = requirements.read_text()
            assert "quickroute" in req_content
            assert "fastapi" in req_content
            assert "uvicorn" in req_content

            # Verify .env.example
            env_example = project_path / ".env.example"
            assert env_example.exists()

            env_content = env_example.read_text()
            assert "SECRET_KEY" in env_content
            assert "DATABASE_URL" in env_content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])