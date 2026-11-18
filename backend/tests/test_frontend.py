import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
UIS = [FRONTEND / "lab", FRONTEND / "assistant", FRONTEND / "portal"]
FILES = sorted(f for ui in UIS for f in ui.rglob("*.js"))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(FRONTEND)))
def test_module_parses(path):
    """The browser loads these as ES modules; a syntax error blanks a whole page."""
    proc = subprocess.run(["node", "--input-type=module", "--check"], input=path.read_text(), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_ui_has_no_inline_script_or_innerhtml():
    """The CSP forbids inline script; innerHTML would be an XSS vector for transcripts and prompts."""
    for ui in UIS:
        html = (ui / "index.html").read_text()
        assert "<script>" not in html and "onclick=" not in html
    for path in FILES:
        assert "innerHTML" not in path.read_text(), f"{path.name} uses innerHTML"


def test_owner_app_routes_and_relative_imports_all_exist():
    """A renamed or deleted screen would otherwise only show up as a blank page on a phone."""
    import re
    app = FRONTEND / "assistant"
    for rel in re.findall(r"import\('\./(views/[a-z]+\.js)'\)", (app / "app.js").read_text()):
        assert (app / rel).exists(), rel
    for f in app.rglob("*.js"):
        for rel in re.findall(r"from '(\.{1,2}/[^']+)'", f.read_text()):
            assert (f.parent / rel).resolve().exists(), (f.name, rel)
    html = (app / "index.html").read_text()
    for asset in re.findall(r'(?:href|src)="((?!http)[^"]+\.(?:css|js))"', html):
        assert (app / asset).exists(), asset
