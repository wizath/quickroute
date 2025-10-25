#!/usr/bin/env python3
"""
QuickRoute Test Runner

Convenient script to run different test suites with various options.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="QuickRoute Test Runner")
    parser.add_argument(
        "test_type",
        choices=["all", "unit", "integration", "auth", "jobs", "websocket", "plugins", "middleware", "managers", "router"],
        help="Type of tests to run"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage reporting"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for changes and re-run tests"
    )
    parser.add_argument(
        "--failed-first",
        action="store_true",
        help="Run failed tests first"
    )

    args = parser.parse_args()

    # Build base pytest command
    cmd = ["python", "-m", "pytest"]

    # Add coverage if requested
    if args.coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term-missing"])

    # Add verbose option
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add parallel option
    if args.parallel:
        cmd.extend(["-n", "auto"])

    # Add watch option
    if args.watch:
        cmd.append("--watch")

    # Add failed-first option
    if args.failed_first:
        cmd.append("--lf")

    # Determine test files based on type
    test_files = {
        "all": ["tests/"],
        "unit": ["tests/test_managers.py", "tests/test_auth.py", "tests/test_middleware.py"],
        "integration": ["tests/test_integration.py"],
        "auth": ["tests/test_auth.py"],
        "jobs": ["tests/test_jobs.py"],
        "websocket": ["tests/test_websocket.py"],
        "plugins": ["tests/test_plugins.py"],
        "middleware": ["tests/test_middleware.py"],
        "managers": ["tests/test_managers.py"],
        "router": ["tests/test_router.py"],
    }

    if args.test_type in test_files:
        cmd.extend(test_files[args.test_type])
    else:
        print(f"Unknown test type: {args.test_type}")
        return 1

    # Change to project directory
    project_root = Path(__file__).parent.parent
    original_dir = Path.cwd()

    try:
        import os
        os.chdir(project_root)

        # Run the tests
        success = run_command(cmd, f"{args.test_type.title()} tests")

        if success:
            print(f"\n✅ {args.test_type.title()} tests passed!")
            if args.coverage:
                print(f"📊 Coverage report generated in htmlcov/index.html")
        else:
            print(f"\n❌ {args.test_type.title()} tests failed!")
            return 1

        return 0

    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    sys.exit(main())