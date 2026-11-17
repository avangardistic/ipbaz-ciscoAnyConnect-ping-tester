"""تست‌های بارگذاری پیکربندی."""
import os
import pytest

from vpn_tester import config as cfg


# ---------- credentials ----------

def test_load_config_missing_credentials(no_env_file, monkeypatch):
    monkeypatch.delenv("VPN_USERNAME", raising=False)
    monkeypatch.delenv("VPN_PASSWORD", raising=False)
    with pytest.raises(cfg.ConfigError, match="VPN_USERNAME"):
        cfg.load_config(require_credentials=True)


def test_load_config_missing_password_only(no_env_file, monkeypatch):
    monkeypatch.setenv("VPN_USERNAME", "u")
    monkeypatch.delenv("VPN_PASSWORD", raising=False)
    with pytest.raises(cfg.ConfigError, match="VPN_PASSWORD"):
        cfg.load_config(require_credentials=True)


def test_load_config_with_credentials(no_env_file, fake_env):
    c = cfg.load_config(require_credentials=True)
    assert c.username == "test_user"
    assert c.password == "test_pass"


def test_load_config_skip_credentials(no_env_file, monkeypatch):
    monkeypatch.delenv("VPN_USERNAME", raising=False)
    monkeypatch.delenv("VPN_PASSWORD", raising=False)
    c = cfg.load_config(require_credentials=False)
    assert c.username == ""


# ---------- cert/script ----------

def test_load_config_with_cert_hash(no_env_file, fake_env, monkeypatch):
    monkeypatch.setenv("VPN_CERT_HASH", "pin-sha256:ABC=")
    assert cfg.load_config().cert_hash == "pin-sha256:ABC="


def test_load_config_empty_cert_hash(no_env_file, fake_env, monkeypatch):
    monkeypatch.setenv("VPN_CERT_HASH", "   ")
    assert cfg.load_config().cert_hash == ""


def test_load_config_with_script_path(no_env_file, fake_env, monkeypatch):
    monkeypatch.setenv("VPN_SCRIPT", r"C:\x.js")
    assert cfg.load_config().script_path == r"C:\x.js"


# ---------- timeouts ----------

def test_load_config_custom_timeout(no_env_file, fake_env, monkeypatch):
    monkeypatch.setenv("CONNECT_TIMEOUT", "60")
    assert cfg.load_config().connect_timeout == 60


def test_load_config_invalid_timeout(no_env_file, fake_env, monkeypatch):
    monkeypatch.setenv("CONNECT_TIMEOUT", "abc")
    with pytest.raises(cfg.ConfigError):
        cfg.load_config()


# ---------- domains precedence ----------

def test_domains_default_when_nothing(no_env_file, fake_env, monkeypatch):
    monkeypatch.delenv("VPN_DOMAINS", raising=False)
    monkeypatch.setattr(cfg, "DOMAINS_FILE", cfg.PROJECT_ROOT / "__nonexistent__.txt")
    c = cfg.load_config()
    assert c.domains == cfg.DEFAULT_DOMAINS


def test_vpn_domains_env_priority(no_env_file, fake_env, monkeypatch):
    monkeypatch.setenv("VPN_DOMAINS", "a.com, b.com")
    assert cfg.load_config().domains == ("a.com", "b.com")


def test_domains_from_file(no_env_file, fake_env, monkeypatch, tmp_path):
    f = tmp_path / "domains.txt"
    f.write_text("# c\ncustom1.com\ncustom2.com\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "DOMAINS_FILE", f)
    monkeypatch.delenv("VPN_DOMAINS", raising=False)
    c = cfg.load_config()
    assert c.domains == ("custom1.com", "custom2.com")


def test_env_overrides_file(no_env_file, fake_env, monkeypatch, tmp_path):
    f = tmp_path / "domains.txt"
    f.write_text("file.com\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "DOMAINS_FILE", f)
    monkeypatch.setenv("VPN_DOMAINS", "env.com")
    assert cfg.load_config().domains == ("env.com",)


# ---------- file helpers ----------

def test_load_domains_file_nonexistent(tmp_path):
    assert cfg.load_domains_file(tmp_path / "nope.txt") == []


def test_load_domains_file_comments(tmp_path):
    f = tmp_path / "d.txt"
    f.write_text("# header\na.com\n\n# x\nb.com # trailing\n", encoding="utf-8")
    assert cfg.load_domains_file(f) == ["a.com", "b.com"]


def test_load_domains_file_skips_blank(tmp_path):
    f = tmp_path / "d.txt"
    f.write_text("a.com\n\n\n   \nb.com\n", encoding="utf-8")
    assert cfg.load_domains_file(f) == ["a.com", "b.com"]


def test_save_domains_file_dedupes(tmp_path):
    f = tmp_path / "d.txt"
    cfg.save_domains_file(f, ["a.com", "b.com", "a.com"])
    content = f.read_text(encoding="utf-8-sig")
    assert content.count("a.com") == 1
    assert content.count("b.com") == 1


def test_save_load_roundtrip(tmp_path):
    f = tmp_path / "d.txt"
    original = ["x.com", "y.com", "z.com"]
    cfg.save_domains_file(f, original)
    assert cfg.load_domains_file(f) == original


# ---------- retries ----------

def test_vpn_retries_from_env(no_env_file, fake_env, monkeypatch):
    monkeypatch.setenv("VPN_RETRIES", "3")
    assert cfg.load_config().retries == 3


def test_vpn_retries_default(no_env_file, fake_env, monkeypatch):
    monkeypatch.delenv("VPN_RETRIES", raising=False)
    assert cfg.load_config().retries == 0


# ---------- BOM ----------

def test_env_file_with_bom(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_bytes(b"\xef\xbb\xbfVPN_USERNAME=u\nVPN_PASSWORD=p\n")
    for k in ("VPN_USERNAME", "VPN_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)
    val = os.environ.get("VPN_USERNAME", "")
    for k in ("VPN_USERNAME", "VPN_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert val in ("u", "\ufeffu")