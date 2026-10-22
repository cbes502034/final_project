"""共用橫幅切換、搜尋鍵盤操作與響應式狀態。實際尺寸另由瀏覽器驗證。"""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_shared_header_modes_and_search_interaction():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is unavailable')
    repo = Path(__file__).resolve().parents[2]
    subprocess.run([node, str(repo / 'backend/tests/fixtures/page_header.js'), str(repo)],
                   check=True, capture_output=True)
