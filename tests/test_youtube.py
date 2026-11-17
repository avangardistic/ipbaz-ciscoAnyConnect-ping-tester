from unittest.mock import patch, MagicMock
from vpn_tester import youtube


def test_check_dns_success():
    with patch("socket.gethostbyname", return_value="142.250.1.1"):
        ok, val = youtube.check_dns()
        assert ok and val == "142.250.1.1"


def test_check_dns_failure():
    import socket
    with patch("socket.gethostbyname", side_effect=socket.gaierror):
        ok, _ = youtube.check_dns()
        assert not ok


def test_check_tcp_success():
    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)
    with patch("socket.create_connection", return_value=fake_sock):
        ok, _ = youtube.check_tcp()
        assert ok


def test_check_tcp_timeout():
    import socket
    with patch("socket.create_connection", side_effect=socket.timeout):
        ok, detail = youtube.check_tcp()
        assert not ok and "timeout" in detail


def test_check_http_robots_success(mock_youtube_200):
    with patch("urllib.request.urlopen", return_value=mock_youtube_200):
        ok, _ = youtube.check_http_robots()
        assert ok


def test_check_http_robots_429():
    from urllib.error import HTTPError
    with patch("urllib.request.urlopen",
               side_effect=HTTPError("u", 429, "Too Many", {}, None)):
        ok, detail = youtube.check_http_robots()
        assert not ok and "429" in detail


def test_diagnose_full_success(mock_youtube_200):
    with patch.object(youtube, "check_dns", return_value=(True, "1.2.3.4")), \
         patch.object(youtube, "check_egress_ip", return_value=("5.6.7.8", "OK")), \
         patch.object(youtube, "check_tcp", return_value=(True, "connected")), \
         patch.object(youtube, "check_http_robots", return_value=(True, "OK")):
        d = youtube.diagnose()
        assert d["youtube_ok"] is True
        assert "دسترس" in d["interpretation"]


def test_diagnose_tcp_failure():
    with patch.object(youtube, "check_dns", return_value=(True, "1.2.3.4")), \
         patch.object(youtube, "check_egress_ip", return_value=("5.6.7.8", "OK")), \
         patch.object(youtube, "check_tcp", return_value=(False, "timeout")):
        d = youtube.diagnose()
        assert d["youtube_ok"] is False
        assert "روتینگ" in d["interpretation"]


def test_diagnose_anti_bot():
    with patch.object(youtube, "check_dns", return_value=(True, "1.2.3.4")), \
         patch.object(youtube, "check_egress_ip", return_value=("5.6.7.8", "OK")), \
         patch.object(youtube, "check_tcp", return_value=(True, "connected")), \
         patch.object(youtube, "check_http_robots", return_value=(False, "HTTP 429")):
        d = youtube.diagnose()
        assert d["youtube_ok"] is False
        assert "anti-bot" in d["interpretation"]