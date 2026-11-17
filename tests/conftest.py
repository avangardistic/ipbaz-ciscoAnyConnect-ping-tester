import pytest
from unittest.mock import MagicMock

from vpn_tester import config as cfg


@pytest.fixture
def fake_env(monkeypatch):
    monkeypatch.setenv("VPN_USERNAME", "test_user")
    monkeypatch.setenv("VPN_PASSWORD", "test_pass")


@pytest.fixture
def no_env_file(tmp_path, monkeypatch):
    """
    جلوگیری از خوانده شدن فایل .env واقعی در ریشه پروژه در طول تست‌ها.

    بدون این fixture، load_config() فایل .env واقعی را بارگذاری می‌کند و
    تست‌های «بدون اعتبارنامه» شکست می‌خورند چون متغیر دوباره populate می‌شود.
    """
    monkeypatch.setattr(cfg, "ENV_FILE", tmp_path / "does_not_exist.env")


@pytest.fixture
def mock_youtube_200():
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = b"<html><title>YouTube</title></html>"
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp