#!/usr/bin/env python3
"""
Standalone test runner for document loaders.
Bypasses the main conftest.py that has import errors.
"""

import asyncio
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Import test framework
import pytest


def main():
    """Run the loader tests standalone."""
    test_file = Path(__file__).parent / "test_loaders.py"
    
    # Run pytest on just this file
    exit_code = pytest.main([
        str(test_file),
        "-v",
        "--tb=short",
        "--no-cov",
        "-p", "no:warnings",
    ])
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
