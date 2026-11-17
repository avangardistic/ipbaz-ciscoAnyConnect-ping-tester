"""تست‌های مدیریت جلسه‌ی openconnect."""
from unittest.mock import patch, MagicMock
import pytest
from vpn_tester import vpn


@pytest.fixture(autouse=True)
def _clear_cache():
    vpn._CERT_HASH_CACHE.clear()
    yield
    vpn._CERT_HASH_CACHE.clear()


def _fake_proc(pid=1234):
    p = MagicMock()
    p.pid = pid
    p.poll.return_value = None
    return p


def test_extract_cert_hash_from_servercert_pattern():
    assert vpn._extract_cert_hash(
        "--servercert pin-sha256:AbCdEf123=+"
    ) == "pin-sha256:AbCdEf123=+"


def test_extract_cert_hash_from_bare_pattern():
    assert vpn._extract_cert_hash("pin-sha256:XY12+/=abc") == "pin-sha256:XY12+/=abc"


def test_extract_cert_hash_none():
    assert vpn._extract_cert_hash("other error") is None
    assert vpn._extract_cert_hash("") is None


def test_wait_for_tunnel_ready_success(tmp_path):
    log = tmp_path / "t.log"
    log.write_text("Connected as 10.0.0.1\nConfigured as 10.0.0.2\n", encoding="utf-8")
    ready, reason = vpn._wait_for_tunnel_ready(log, max_wait=2, initial_wait=0)
    assert ready is True


def test_wait_for_tunnel_ready_timeout(tmp_path):
    log = tmp_path / "t.log"
    log.write_text("Connected as 10.0.0.1\n", encoding="utf-8")
    ready, reason = vpn._wait_for_tunnel_ready(log, max_wait=1, initial_wait=0.1)
    assert ready is False
    assert "تمام شد" in reason


def test_wait_for_tunnel_ready_auth_fail(tmp_path):
    log = tmp_path / "t.log"
    log.write_text("Failed to complete authentication\n", encoding="utf-8")
    ready, reason = vpn._wait_for_tunnel_ready(log, max_wait=2, initial_wait=0)
    assert ready is False
    assert "احراز هویت" in reason


def test_wait_for_tunnel_ready_lowercase_configured(tmp_path):
    """مهم: Configured as با هر case ای تشخیص داده شود."""
    log = tmp_path / "t.log"
    log.write_text("CONFIGURED AS 10.0.0.2\n", encoding="utf-8")
    ready, _ = vpn._wait_for_tunnel_ready(log, max_wait=2, initial_wait=0)
    assert ready is True


def test_session_success_direct(tmp_path):
    fake = _fake_proc()
    with patch.object(vpn, "_start_openconnect", return_value=(fake, "")) as start, \
         patch.object(vpn, "_kill_process"):
        with vpn.openconnect_session(
            "d.com", "u", "p", cert_hash="pin-sha256:ABC=",
            pid_dir=tmp_path, wait_tunnel_ready=False,
        ) as pid:
            assert pid == 1234
        assert start.call_args.args[3] == "pin-sha256:ABC="


def test_session_retry_on_cert_error(tmp_path):
    stderr = "--servercert pin-sha256:DISCOVERED=\n"
    fake = _fake_proc(pid=5678)
    calls = []

    def fake_start(domain, username, password, cert_hash, **kw):
        calls.append(cert_hash)
        if len(calls) == 1:
            return None, stderr
        return fake, ""

    with patch.object(vpn, "_start_openconnect", side_effect=fake_start), \
         patch.object(vpn, "_kill_process"):
        with vpn.openconnect_session(
            "d.com", "u", "p", pid_dir=tmp_path, wait_tunnel_ready=False,
        ) as pid:
            assert pid == 5678

    assert calls == ["", "pin-sha256:DISCOVERED="]
    assert vpn._get_cached_hash() == "pin-sha256:DISCOVERED="


def test_session_uses_cache(tmp_path):
    vpn._set_cached_hash("pin-sha256:CACHED=")
    fake = _fake_proc()
    with patch.object(vpn, "_start_openconnect", return_value=(fake, "")) as start, \
         patch.object(vpn, "_kill_process"):
        with vpn.openconnect_session(
            "d2.com", "u", "p", pid_dir=tmp_path, wait_tunnel_ready=False,
        ):
            pass
    assert start.call_args.args[3] == "pin-sha256:CACHED="


def test_session_fails_no_hash(tmp_path):
    with patch.object(vpn, "_start_openconnect", return_value=(None, "auth failed")):
        with pytest.raises(vpn.VPNError, match="auth failed"):
            with vpn.openconnect_session(
                "d.com", "u", "p", pid_dir=tmp_path, wait_tunnel_ready=False,
            ):
                pass


def test_session_kills_in_finally(tmp_path):
    fake = _fake_proc()
    with patch.object(vpn, "_start_openconnect", return_value=(fake, "")), \
         patch.object(vpn, "_kill_process") as kill:
        with pytest.raises(RuntimeError):
            with vpn.openconnect_session(
                "d.com", "u", "p", pid_dir=tmp_path, wait_tunnel_ready=False,
            ):
                raise RuntimeError("boom")
        kill.assert_called_once_with(fake)


def test_session_tunnel_not_ready_raises(tmp_path):
    fake = _fake_proc()
    with patch.object(vpn, "_start_openconnect", return_value=(fake, "")), \
         patch.object(vpn, "_kill_process"), \
         patch.object(vpn, "_wait_for_tunnel_ready", return_value=(False, "timeout")):
        with pytest.raises(vpn.VPNError, match="تونل آماده نشد"):
            with vpn.openconnect_session(
                "d.com", "u", "p", pid_dir=tmp_path,
                wait_tunnel_ready=True, tunnel_ready_timeout=0.1,
            ):
                pass


def test_session_tunnel_ready_fixes_windows(tmp_path):
    """اگر Configured as دیده شود، _fix_windows_tunnel صدا زده می‌شود."""
    fake = _fake_proc()
    with patch.object(vpn, "_start_openconnect", return_value=(fake, "")), \
         patch.object(vpn, "_kill_process"), \
         patch.object(vpn, "_wait_for_tunnel_ready", return_value=(True, "ok")), \
         patch.object(vpn, "_fix_windows_tunnel", return_value=(True, "adapter=fake ok")) as fix:
        with vpn.openconnect_session(
            "d.com", "u", "p", pid_dir=tmp_path, wait_tunnel_ready=True,
        ) as pid:
            assert pid == 1234
        fix.assert_called_once()


def test_session_tunnel_ready_but_fix_fails_still_returns(tmp_path):
    """اگر _fix_windows_tunnel شکست بخورد، جلسه ادامه می‌یابد (فقط هشدار)."""
    fake = _fake_proc()
    with patch.object(vpn, "_start_openconnect", return_value=(fake, "")), \
         patch.object(vpn, "_kill_process"), \
         patch.object(vpn, "_wait_for_tunnel_ready", return_value=(True, "ok")), \
         patch.object(vpn, "_fix_windows_tunnel", return_value=(False, "tun adapter پیدا نشد")):
        with vpn.openconnect_session(
            "d.com", "u", "p", pid_dir=tmp_path, wait_tunnel_ready=True,
        ) as pid:
            assert pid == 1234
        # بررسی اینکه پیام در لاگ نوشته شده
        log_files = list(tmp_path.glob(".openconnect_*.log"))
        assert any("NETFIX" in f.read_text(encoding="utf-8") for f in log_files)