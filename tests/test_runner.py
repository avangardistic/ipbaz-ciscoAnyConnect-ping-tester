"""تست‌های ارکستراتور runner."""
from unittest.mock import patch, MagicMock

import pytest

from vpn_tester.config import Config
from vpn_tester.vpn import VPNError
from vpn_tester import runner


def _cfg(domains=("a.com", "b.com")):
    return Config(
        username="u", password="p", domains=domains,
        settle_time=0.0, between_tests_delay=0.0,
    )


def _diag_ok():
    return {
        "dns_ok": True, "dns_ip": "1.2.3.4",
        "tcp_ok": True, "tcp_detail": "connected",
        "http_ok": True, "http_detail": "OK",
        "egress_ip": "5.6.7.8",
        "youtube_ok": True,
        "interpretation": "✅ YouTube در دسترس است",
    }


def _diag_vpn_only():
    d = _diag_ok()
    d["http_ok"] = False
    d["http_detail"] = "HTTP 429"
    d["youtube_ok"] = False
    d["interpretation"] = "YouTube anti-bot فعال شد (HTTP 429)"
    return d


def _fake_session_ctx(pid=42):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=pid)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ---------- تست‌های پایه (فقط از _test_domain_once استفاده می‌کنند) ----------

def test_dns_fail_short_circuits():
    with patch.object(runner, "resolve_host", return_value=None), \
         patch.object(runner, "openconnect_session") as oc:
        r = runner._test_domain_once("a.com", _cfg())
        assert r.dns_ok is False
        assert r.status == "unreachable"
        oc.assert_not_called()


def test_vpn_fail():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(side_effect=VPNError("boom"))
    ctx.__exit__ = MagicMock(return_value=False)

    with patch.object(runner, "resolve_host", return_value="1.2.3.4"), \
         patch.object(runner, "openconnect_session", return_value=ctx):
        r = runner._test_domain_once("a.com", _cfg())
        assert r.dns_ok is True
        assert r.vpn_ok is False
        assert r.status == "dns_ok"
        assert "boom" in r.detail


def test_vpn_ok_youtube_fail():
    with patch.object(runner, "resolve_host", return_value="1.2.3.4"), \
         patch.object(runner, "openconnect_session",
                      return_value=_fake_session_ctx(pid=42)), \
         patch.object(runner.youtube, "diagnose",
                      return_value=_diag_vpn_only()):
        r = runner._test_domain_once("a.com", _cfg())
        assert r.vpn_ok is True
        assert r.youtube_ok is False
        assert r.status == "vpn_only"
        assert r.egress_ip == "5.6.7.8"
        assert "anti-bot" in r.interpretation
        assert "PID=42" in r.detail


def test_vpn_ok_youtube_ok():
    with patch.object(runner, "resolve_host", return_value="1.2.3.4"), \
         patch.object(runner, "openconnect_session",
                      return_value=_fake_session_ctx(pid=42)), \
         patch.object(runner.youtube, "diagnose",
                      return_value=_diag_ok()):
        r = runner._test_domain_once("a.com", _cfg())
        assert r.vpn_ok is True
        assert r.youtube_ok is True
        assert r.status == "youtube_ok"


# ---------- to_dict ----------

def test_to_dict_includes_status_property():
    from vpn_tester.runner import TestResult
    r = TestResult(
        domain="x.com", dns_ok=True, vpn_ok=True, youtube_ok=True,
        detail="d", elapsed=1.0, egress_ip="1.2.3.4",
        interpretation="ok",
    )
    d = r.to_dict()
    assert "status" in d
    assert d["status"] == "youtube_ok"
    assert d["domain"] == "x.com"
    assert d["youtube_ok"] is True
    assert d["egress_ip"] == "1.2.3.4"


def test_to_dict_status_for_each_branch():
    from vpn_tester.runner import TestResult
    cases = [
        (dict(dns_ok=False, vpn_ok=False, youtube_ok=False), "unreachable"),
        (dict(dns_ok=True,  vpn_ok=False, youtube_ok=False), "dns_ok"),
        (dict(dns_ok=True,  vpn_ok=True,  youtube_ok=False), "vpn_only"),
        (dict(dns_ok=True,  vpn_ok=True,  youtube_ok=True),  "youtube_ok"),
    ]
    for kwargs, expected in cases:
        r = TestResult(domain="d", detail="", elapsed=0.0, **kwargs)
        assert r.to_dict()["status"] == expected


# ---------- run_all ----------

def test_run_all_progress():
    from vpn_tester.runner import TestResult
    fake = TestResult(
        domain="x", dns_ok=True, vpn_ok=True, youtube_ok=True,
        detail="", elapsed=0.1,
    )
    calls = []
    with patch.object(runner, "test_domain", return_value=fake):
        results = runner.run_all(_cfg(), on_progress=lambda i, t, r: calls.append((i, t)))

    assert len(results) == 2
    assert calls == [(1, 2), (2, 2)]


# ---------- retry logic ----------

def test_test_domain_retries_on_vpn_fail():
    """retry اگر dns_ok ولی vpn_ok=False باشد."""
    from vpn_tester.runner import TestResult
    fail = TestResult("x", True, False, False, "err", 0.1)

    with patch.object(runner, "_test_domain_once", return_value=fail) as inner:
        r = runner.test_domain("x", _cfg(), retries=2, retry_delay=0.0)
        assert inner.call_count == 3
        assert r.vpn_ok is False
        assert "[after 3 attempts]" in r.detail


def test_test_domain_no_retry_on_dns_fail():
    """retry اگر DNS شکست خورد انجام نمی‌شود."""
    from vpn_tester.runner import TestResult
    fail = TestResult("x", False, False, False, "dns err", 0.1)

    with patch.object(runner, "_test_domain_once", return_value=fail) as inner:
        r = runner.test_domain("x", _cfg(), retries=2, retry_delay=0.0)
        assert inner.call_count == 1


def test_test_domain_stops_on_success():
    """retry متوقف می‌شود به محض موفقیت."""
    from vpn_tester.runner import TestResult
    fail = TestResult("x", True, True, False, "", 0.1)
    success = TestResult("x", True, True, True, "", 0.1)

    with patch.object(runner, "_test_domain_once", side_effect=[fail, success]) as inner:
        r = runner.test_domain("x", _cfg(), retries=3, retry_delay=0.0)
        assert inner.call_count == 2
        assert r.youtube_ok is True
        assert "[attempt 2]" in r.detail