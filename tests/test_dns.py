from unittest.mock import patch
import socket
from vpn_tester import dns


def test_resolve_success():
    with patch("socket.gethostbyname", return_value="1.2.3.4"):
        assert dns.resolve_host("example.com") == "1.2.3.4"


def test_resolve_gaierror():
    with patch("socket.gethostbyname", side_effect=socket.gaierror):
        assert dns.resolve_host("bad.com") is None


def test_resolve_timeout():
    import time
    def slow(_):
        time.sleep(2)
        return "9.9.9.9"
    with patch("socket.gethostbyname", side_effect=slow):
        assert dns.resolve_host("slow.com", timeout=0.3) is None