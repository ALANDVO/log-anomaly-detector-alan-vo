import pytest
from app.services.parser import LogParser

def test_extract_template_masks_variables():
    msg = "User 192.168.1.50 accessed /api/v1/orders/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d status 200 in 45ms"
    tpl_id, pattern, params = LogParser.extract_template(msg)
    assert tpl_id.startswith("tpl_")
    assert "<*>" in pattern
    assert "User <*>" in pattern
    assert len(params) >= 3

def test_extract_level_and_clean_with_timestamp():
    raw = "2026-10-07T14:32:01.123Z [ERROR] Failed to connect to db-proxy"
    lvl, cleaned, ts = LogParser.extract_level_and_clean(raw)
    assert lvl == "ERROR"
    assert "Failed to connect to db-proxy" in cleaned
    assert ts == "2026-10-07T14:32:01.123Z"

def test_extract_level_default_when_missing():
    raw = "Informational status message without explicit level header"
    lvl, cleaned, ts = LogParser.extract_level_and_clean(raw, default_level="INFO")
    assert lvl == "INFO"
    assert cleaned == raw
    assert ts is None

def test_extract_template_empty_or_whitespace():
    tpl_id, pattern, params = LogParser.extract_template("   ")
    assert pattern == "<empty_log>"
    assert params == []

def test_body_level_words_do_not_override_explicit_level():
    info_body = "Request finished with no error observed by the client"
    lvl, cleaned, ts = LogParser.extract_level_and_clean(info_body, default_level="INFO")
    assert lvl == "INFO"
    assert cleaned == info_body
    assert ts is None

    error_body = "Cache info refreshed for session key after deploy"
    lvl, _, _ = LogParser.extract_level_and_clean(error_body, default_level="ERROR")
    assert lvl == "ERROR"

def test_prefix_level_still_wins_over_default():
    raw = "auth-service ERROR connection refused to db-proxy"
    lvl, _, ts = LogParser.extract_level_and_clean(raw, default_level="INFO")
    assert lvl == "ERROR"
    assert ts is None

    bracketed = "[WARN] Client cancelled request before response completed"
    lvl, _, _ = LogParser.extract_level_and_clean(bracketed, default_level="INFO")
    assert lvl == "WARN"
