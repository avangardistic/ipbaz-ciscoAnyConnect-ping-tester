"""تشخیص دقیق دسترسی به YouTube: DNS / TCP / HTTP / Egress IP."""
from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request

CHECK_HOST = "www.youtube.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
EGRESS_CHECK_URL = "https://api.ipify.org"


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def check_dns(host: str = CHECK_HOST) -> tuple[bool, str]:
    """آیا DNS برای host کار می‌کند و به چه IP حل می‌شود؟"""
    try:
        ip = socket.gethostbyname(host)
        return True, ip
    except socket.gaierror as e:
        return False, f"DNS error: {e}"


def check_tcp(
    host: str = CHECK_HOST, port: int = 443, timeout: float = 8
) -> tuple[bool, str]:
    """آیا TCP به host:port وصل می‌شود؟ (بدون HTTP - فقط روتینگ را می‌سنجد)"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "connected"
    except socket.timeout:
        return False, "timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_http_robots(timeout: float = 10) -> tuple[bool, str]:
    """
    HTTPS به /robots.txt — endpoint استاتیک که معمولاً anti-bot را
    تحریک نمی‌کند، برخلاف صفحه‌ی اصلی.
    """
    url = f"https://{CHECK_HOST}/robots.txt"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            if r.status != 200:
                return False, f"HTTP {r.status}"
            body = r.read(500).decode("utf-8", "ignore").lower()
            if "disallow" in body or "user-agent" in body or "youtube" in body:
                return True, "OK"
            return False, f"unexpected body: {body[:80]!r}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_egress_ip(timeout: float = 8) -> tuple[str | None, str]:
    """
    IP عمومی که اینترنت ما را می‌بیند.
    اگر این IP با IP لوکال یکی نباشد، ترافیک از VPN رد می‌شود.
    اگر یکی باشد، split tunnel فعال است.
    """
    try:
        req = urllib.request.Request(
            EGRESS_CHECK_URL, headers={"User-Agent": "curl/8"}
        )
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            ip = r.read().decode("utf-8", "ignore").strip()
            return ip or None, "OK"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def diagnose(timeout: float = 10) -> dict:
    """
    تشخیص کامل. برمی‌گرداند:
      dns_ok, dns_ip,
      tcp_ok, tcp_detail,
      http_ok, http_detail,
      egress_ip, routing_ok (None=نامشخص),
      youtube_ok (نتیجه‌ی نهایی), interpretation (رشته‌ی فارسی)
    """
    result = {
        "dns_ok": False, "dns_ip": None,
        "tcp_ok": False, "tcp_detail": "",
        "http_ok": False, "http_detail": "",
        "egress_ip": None,
        "youtube_ok": False,
        "interpretation": "",
    }

    # ۱. DNS
    dns_ok, dns_detail = check_dns()
    result["dns_ok"] = dns_ok
    result["dns_ip"] = dns_detail if dns_ok else None

    # ۲. Egress IP (تشخیص split tunnel)
    egress, egress_err = check_egress_ip(timeout=timeout)
    result["egress_ip"] = egress

    # ۳. TCP
    tcp_ok, tcp_detail = check_tcp(timeout=timeout)
    result["tcp_ok"] = tcp_ok
    result["tcp_detail"] = tcp_detail

    # ۴. HTTP (فقط اگر TCP موفق بود)
    if tcp_ok:
        http_ok, http_detail = check_http_robots(timeout=timeout)
        result["http_ok"] = http_ok
        result["http_detail"] = http_detail

    result["youtube_ok"] = result["dns_ok"] and result["tcp_ok"] and result["http_ok"]

    # ۵. تفسیر
    if not result["dns_ok"]:
        result["interpretation"] = "DNS مسدود — ترافیک به DNS نمی‌رسد"
    elif result["egress_ip"] is None:
        result["interpretation"] = "Egress نامشخص — حتی IP چک هم پاسخ نداد (مشکل روتینگ)"
    elif not result["tcp_ok"]:
        result["interpretation"] = f"TCP به YouTube نمی‌رسد — مشکل روتینگ ({tcp_detail})"
    elif not result["http_ok"] and "429" in result["http_detail"]:
        result["interpretation"] = "YouTube anti-bot فعال شد (HTTP 429) — از مرورگر امتحان کنید"
    elif not result["http_ok"] and "403" in result["http_detail"]:
        result["interpretation"] = "YouTube IP را مسدود کرده (HTTP 403)"
    elif not result["http_ok"]:
        result["interpretation"] = f"HTTP ناموفق ({result['http_detail']})"
    else:
        result["interpretation"] = "✅ YouTube در دسترس است"

    return result