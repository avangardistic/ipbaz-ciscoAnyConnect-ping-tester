"""تست‌های کشف زیردامنه (بدون تماس واقعی با شبکه)."""
from unittest.mock import patch, MagicMock
import pytest

from vpn_tester import discovery


def test_generate_pattern_candidates():
    c = discovery.generate_pattern_candidates("apibaz.org", max_n=3)
    assert "mcis1.apibaz.org" in c
    assert "mcis3.apibaz.org" in c
    assert "mcis4.apibaz.org" not in c
    assert "shatel1.apibaz.org" in c


def test_generate_word_candidates():
    c = discovery.generate_word_candidates("apibaz.org")
    assert "pro.apibaz.org" in c
    assert "nlwin.apibaz.org" in c


def test_query_crtsh_success():
    fake_resp = MagicMock()
    fake_resp.read.return_value = (
        b'[{"name_value": "a.apibaz.org\\nb.apibaz.org"},'
        b'{"name_value": "*.apibaz.org"}]'
    )
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=fake_resp):
        result = discovery.query_crtsh("apibaz.org")
        assert "a.apibaz.org" in result
        assert "b.apibaz.org" in result
        assert "*.apibaz.org" not in result  # wildcard filter


def test_query_crtsh_network_error():
    from urllib.error import URLError
    with patch("urllib.request.urlopen", side_effect=URLError("no net")):
        assert discovery.query_crtsh("apibaz.org") == set()


def test_probe_host_dns_fail():
    with patch.object(discovery, "resolve_host", return_value=None):
        r = discovery.probe_host("x.com")
        assert r["alive"] is False
        assert r["reason"] == "dns"


def test_probe_host_tcp_ok():
    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)
    with patch.object(discovery, "resolve_host", return_value="1.2.3.4"), \
         patch("socket.create_connection", return_value=fake_sock):
        r = discovery.probe_host("x.com")
        assert r["alive"] is True
        assert r["ip"] == "1.2.3.4"


def test_probe_hosts_parallel_filters_alive():
    def fake_probe(host, timeout=3.0):
        return {"domain": host, "ip": "1.2.3.4",
                "alive": "alive" in host, "reason": ""}

    with patch.object(discovery, "probe_host", side_effect=fake_probe):
        result = discovery.probe_hosts_parallel(
            {"alive1.com", "alive2.com", "dead1.com"}, max_workers=2,
        )
    assert {r["domain"] for r in result} == {"alive1.com", "alive2.com"}


def test_discover_merges_sources():
    with patch.object(discovery, "query_crtsh", return_value={"found.apibaz.org"}), \
         patch.object(discovery, "probe_hosts_parallel",
                      return_value=[{"domain": "found.apibaz.org", "ip": "1.2.3.4",
                                     "alive": True, "reason": "tcp-ok"}]):
        result = discovery.discover(base="apibaz.org", max_n=2, known_domains=set())
    assert result["crtsh"] == {"found.apibaz.org"}
    assert len(result["patterns"]) > 0
    assert len(result["words"]) > 0
    assert len(result["alive"]) == 1
    assert result["newly_discovered"][0]["domain"] == "found.apibaz.org"


def test_discover_excludes_known():
    known = {"mcis1.apibaz.org"}
    captured = {}

    def fake_probe(hosts, **kw):
        captured["hosts"] = set(hosts)
        return []

    with patch.object(discovery, "query_crtsh", return_value=set()), \
         patch.object(discovery, "probe_hosts_parallel", side_effect=fake_probe):
        discovery.discover(base="apibaz.org", max_n=2, known_domains=known)

    assert "mcis1.apibaz.org" not in captured["hosts"]
    assert "mcis2.apibaz.org" in captured["hosts"]