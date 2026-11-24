import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "public/stitch.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "public/stitch.js").read_text(encoding="utf-8")
ROUTING = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))


def test_vercel_root_uses_stitch_ui_and_existing_api_contract():
    assert ROUTING["framework"] is None
    assert {"source": "/", "destination": "/stitch.html"} in ROUTING["rewrites"]
    assert 'id="question-form"' in HTML
    assert "fetch('/api/query'" in SCRIPT
    assert "payload.category" in SCRIPT
    assert "payload.citation" in SCRIPT
    assert "payload.source_updated_at" in SCRIPT


def test_stitch_ui_contains_no_exported_sample_facts_or_sources():
    combined = HTML + SCRIPT
    for mock_content in ("0.94%", "1.68%", "March 2024", "hdfcfund.com", "Scheme Information Document"):
        assert mock_content not in combined
    assert "Facts-only. No investment advice" in HTML
    assert "source_updated_at" in SCRIPT
