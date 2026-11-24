from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "public/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "public/styles.css").read_text(encoding="utf-8").lower()
JAVASCRIPT = (ROOT / "public/app.js").read_text(encoding="utf-8")


def test_vercel_ui_has_required_sections_and_accessibility_contracts():
    required_content = (
        "Groww Facts",
        "Verified sources",
        "Facts only",
        "Mutual fund facts,",
        "Try an example",
        "Ask about a fund",
        'aria-live="polite"',
        "Information is sourced from approved public Groww pages",
    )
    assert all(content in HTML for content in required_content)


def test_vercel_ui_uses_only_approved_palette_hex_values():
    approved = {
        "#00d09c",
        "#008f76",
        "#44475b",
        "#7c7e8c",
        "#f6f6f7",
        "#e5e7eb",
        "#ffffff",
        "#e8faf5",
    }
    import re

    used = set(re.findall(r"#[0-9a-f]{6}", CSS))
    assert used.issubset(approved)


def test_vercel_ui_calls_query_api_and_supports_every_response_state():
    assert 'fetch("/api/query"' in JAVASCRIPT
    categories = (
        "FACTUAL_SUPPORTED",
        "CLARIFICATION_REQUIRED",
        "ADVICE_OR_OPINION",
        "PERFORMANCE_REQUEST",
        "OUT_OF_SCOPE",
        "UNSUPPORTED_BY_SOURCES",
        "SENSITIVE_DATA",
        "SERVICE_ERROR",
    )
    assert all(category in JAVASCRIPT for category in categories)


def test_vercel_ui_contains_no_mojibake():
    combined = HTML + CSS + JAVASCRIPT
    assert "â€" not in combined
    assert "ï¿½" not in combined
