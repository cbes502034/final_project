"""Regression coverage for browser session renewal and logout races."""
import pathlib
import shutil
import subprocess

import pytest


def test_browser_session_renewal():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to execute the browser adapter")
    root = pathlib.Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, str(root / "backend/tests/fixtures/auth_refresh.js"), str(root)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 scenarios passed" in result.stdout
