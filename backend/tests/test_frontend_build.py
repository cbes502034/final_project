"""部署資源版本必須跟著內容變更，避免新版畫面取得舊版 API。"""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def build(source, output):
    node = shutil.which('node')
    if not node:
        pytest.skip('node is unavailable')
    return subprocess.run([node, str(ROOT / 'tools/build_frontend.js'), str(source), str(output)],
                          check=True, capture_output=True, text=True)


def api_url(folder):
    return re.search(r'<script src="(js/api\.js\?v=[^"]+)"', (folder / 'index.html').read_text(encoding='utf-8')).group(1)


def test_asset_versions_follow_contents_and_build_keeps_source_unchanged(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'site'
    shutil.copytree(ROOT / 'frontend', source)
    original = (source / 'index.html').read_bytes()
    build(source, output)
    old_url = api_url(output)
    assert old_url != 'js/api.js?v=193'
    assert old_url.endswith(hashlib.sha256((source / 'js/api.js').read_bytes()).hexdigest()[:16])
    assert (source / 'index.html').read_bytes() == original
    assert (output / 'js/api.js').read_bytes() == (source / 'js/api.js').read_bytes()
    assert 'transactionArchive:' in (output / 'js/api.js').read_text(encoding='utf-8')
    first = (output / 'index.html').read_bytes()
    build(source, output)
    assert (output / 'index.html').read_bytes() == first
    with (source / 'js/api.js').open('a', encoding='utf-8') as asset:
        asset.write('\n// new API release\n')
    build(source, output)
    assert api_url(output) != old_url
    assert '?v=194' in (source / 'index.html').read_text(encoding='utf-8')


def test_deployment_points_to_content_versioned_output():
    render = (ROOT / 'render.yaml').read_text(encoding='utf-8')
    assert 'buildCommand: node tools/build_frontend.js' in render
    assert 'staticPublishPath: ./dist/frontend' in render
