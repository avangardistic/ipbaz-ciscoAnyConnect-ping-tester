"""Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ù¾ÛŒÚ©Ø±Ø¨Ù†Ø¯ÛŒ Ø§Ø² .envØŒ domains.txt Ùˆ Ù…ØªØºÛŒØ±Ù‡Ø§ÛŒ Ù…Ø­ÛŒØ·ÛŒ."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
DOMAINS_FILE = PROJECT_ROOT / "domains.txt"

DEFAULT_DOMAINS: tuple[str, ...] = (
    "mcis1.apibaz.org", "example.invalid", "mcis3.apibaz.org",
    "mcis4.apibaz.org", "example.invalid", "mcis6.apibaz.org",
    "mcis7.apibaz.org", "example.invalid", "mcis9.apibaz.org",
    "mcis10.apibaz.org", "mcipro.apibaz.org", "shatel1.apibaz.org",
    "tci.apibaz.org", "nlwin.apibaz.org",
)


class ConfigError(Exception):
    """Ø®Ø·Ø§ÛŒ Ù¾ÛŒÚ©Ø±Ø¨Ù†Ø¯ÛŒ."""


@dataclass(frozen=True)
class Config:
    username: str
    password: str
    cert_hash: str = ""
    script_path: str = ""
    domains: tuple[str, ...] = DEFAULT_DOMAINS
    connect_timeout: int = 35
    youtube_timeout: int = 12
    settle_time: float = 3.0
    between_tests_delay: float = 2.0
    retries: int = 0
    pid_dir: Path = field(default_factory=lambda: PROJECT_ROOT)


# ---------- helpers Ø¨Ø±Ø§ÛŒ domains.txt ----------

def load_domains_file(path: Path) -> list[str]:
    """
    Ø®ÙˆØ§Ù†Ø¯Ù† domains.txt.
    ÙØ±Ù…Øª: Ù‡Ø± Ø®Ø· ÛŒÚ© Ø¯Ø§Ù…Ù†Ù‡. # Ø´Ø±ÙˆØ¹ Ú©Ø§Ù…Ù†Øª. Ú©Ø§Ù…Ù†Øª Ø§Ù†ØªÙ‡Ø§ÛŒ Ø®Ø· Ø¨Ø§ ' #' Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ù…ÛŒâ€ŒØ´ÙˆØ¯.
    """
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []

    domains: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " #" in line:
            line = line.split(" #")[0].strip()
        if line:
            domains.append(line)
    return domains


def save_domains_file(path: Path, domains: list[str], include_header: bool = True) -> None:
    """Ù†ÙˆØ´ØªÙ† domains.txt Ø¨Ø§ Ø­ÙØ¸ ØªØ±ØªÛŒØ¨ Ùˆ Ø­Ø°Ù ØªÚ©Ø±Ø§Ø±ÛŒ."""
    lines: list[str] = []
    if include_header:
        lines = [
            "# Ù„ÛŒØ³Øª Ø¯Ø§Ù…Ù†Ù‡â€ŒÙ‡Ø§ÛŒ Cisco AnyConnect",
            "# Ù‡Ø± Ø®Ø· ÛŒÚ© Ø¯Ø§Ù…Ù†Ù‡. # Ø¨Ø±Ø§ÛŒ Ú©Ø§Ù…Ù†Øª.",
            "",
        ]
    seen: set[str] = set()
    for d in domains:
        d = d.strip()
        if d and d not in seen:
            seen.add(d)
            lines.append(d)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


# ---------- Ø®ÙˆØ§Ù†Ø¯Ù† Ø³Ø§ÛŒØ± Ù…Ù‚Ø§Ø¯ÛŒØ± ----------

def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Ù…Ù‚Ø¯Ø§Ø± {name} Ø¨Ø§ÛŒØ¯ Ø¹Ø¯Ø¯ Ø¨Ø§Ø´Ø¯ØŒ Ø¯Ø±ÛŒØ§ÙØª Ø´Ø¯: {raw!r}") from exc


def _read_domains() -> tuple[str, ...]:
    """
    Ø§ÙˆÙ„ÙˆÛŒØª:
      1. VPN_DOMAINS (env) â€” Ø¨Ø§Ù„Ø§ØªØ±ÛŒÙ† Ø§ÙˆÙ„ÙˆÛŒØª (Ø¨Ø±Ø§ÛŒ CI/Ø§Ø³Ú©Ø±ÛŒÙ¾Øª)
      2. domains.txt â€” Ø§Ú¯Ø± ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø´Øª Ùˆ Ù¾Ø± Ø¨ÙˆØ¯
      3. DEFAULT_DOMAINS â€” Ù¾ÛŒØ´â€ŒÙØ±Ø¶
    """
    # Û±. env
    raw = os.getenv("VPN_DOMAINS", "").strip()
    if raw:
        parsed = tuple(d.strip() for d in raw.split(",") if d.strip())
        if parsed:
            return parsed

    # Û². domains.txt
    file_domains = load_domains_file(DOMAINS_FILE)
    if file_domains:
        return tuple(file_domains)

    # Û³. default
    return DEFAULT_DOMAINS


def load_config(require_credentials: bool = True) -> Config:
    load_dotenv(ENV_FILE, override=False)

    username = os.getenv("VPN_USERNAME", "").strip()
    password = os.getenv("VPN_PASSWORD", "").strip()
    cert_hash = os.getenv("VPN_CERT_HASH", "").strip()
    script_path = os.getenv("VPN_SCRIPT", "").strip()

    if require_credentials:
        if not username:
            raise ConfigError(
                "VPN_USERNAME ØªÙ†Ø¸ÛŒÙ… Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª. ÙØ§ÛŒÙ„ .env Ø±Ø§ Ø¯Ø± Ø±ÛŒØ´Ù‡ Ù¾Ø±ÙˆÚ˜Ù‡ Ø¨Ø³Ø§Ø²ÛŒØ¯."
            )
        if not password:
            raise ConfigError(
                "VPN_PASSWORD ØªÙ†Ø¸ÛŒÙ… Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª. ÙØ§ÛŒÙ„ .env Ø±Ø§ Ø¯Ø± Ø±ÛŒØ´Ù‡ Ù¾Ø±ÙˆÚ˜Ù‡ Ø¨Ø³Ø§Ø²ÛŒØ¯."
            )

    return Config(
        username=username,
        password=password,
        cert_hash=cert_hash,
        script_path=script_path,
        domains=_read_domains(),
        connect_timeout=_read_int("CONNECT_TIMEOUT", 35),
        youtube_timeout=_read_int("YOUTUBE_TIMEOUT", 12),
        retries=_read_int("VPN_RETRIES", 0),
    )
