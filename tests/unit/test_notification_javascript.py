"""Run the real notification JS in an offline Node DOM/timer harness."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_notification_browser_polling_contract():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the offline JavaScript contract test")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, "tests/js/notifications.test.cjs"], cwd=root,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
