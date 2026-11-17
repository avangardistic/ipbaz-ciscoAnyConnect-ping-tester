"""کشف زیردامنه‌های پنهان apibaz.org (یا هر دامنه‌ی دیگر)."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from .dns import resolve_host


# ---------- الگوهای شماره‌دار ----------
DEFAULT_PATTERNS = [
    "mcis{n}", "mcin{n}", "mci{n}", "mc{n}",
    "shatel{n}", "tci{n}", "nlwin{n}", "nlpro{n}",
    "mtn{n}", "irancell{n}", "rightel{n}",
    "pro{n}", "vip{n}", "test{n}", "backup{n}",
]

# ---------- واژه‌های ثابت ----------
DEFAULT_WORDS = [
    # پرو / VIP
    "pro", "pro1", "pro2", "pro3", "proplus", "promax",
    "vip", "vip1", "vip2", "vip3",
    # تست / dev
    "test", "test1", "test2", "dev", "dev1", "staging",
    # نسخه‌ها
    "backup", "bak", "old", "new",
    # مناطق
    "nl", "nl1", "nl2", "nlwin", "nlpro", "us", "de", "fr", "uk",
    # اپراتورها
    "mci", "mcipro", "mciproplus", "mcipromax",
    "shatel", "shatelpro", "shatelvip",
    "tci", "tcipro", "tcipro1", "tcipro2",
    "irancell", "mtn",
    # پلتفرم
    "win", "windows", "android", "ios",
    # عددی ساده
    "1", "2", "3", "4", "5", "6", "7", "8", "9",
]


def generate_pattern_candidates(base: str, max_n: int = 50) -> set[str]:
    """تولید کاندیدهای شماره‌دار: mcis1..mcis50, mcin1..mcin50, ..."""
    candidates = set()
    for pattern in DEFAULT_PATTERNS:
        for n in range(1, max_n + 1):
            candidates.add(pattern.format(n=n) + "." + base)
    return candidates


def generate_word_candidates(base: str) -> set[str]:
    """تولید کاندیدهای واژه‌ای: pro, vip, nlwin, ..."""
    return {w + "." + base for w in DEFAULT_WORDS}


def query_crtsh(base: str, timeout: float = 30.0) -> set[str]:
    """
    جستجو در Certificate Transparency logs (crt.sh).
    دامنه‌هایی که certificate SSL عمومی دارند را پیدا می‌کند.
    """
    url = f"https://crt.sh/?q=%25.{base}&output=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return set()

    if not isinstance(data, list):
        return set()

    found = set()
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name_value = entry.get("name_value", "")
        for name in str(name_value).split("\n"):
            name = name.strip().lower()
            if not name or "*" in name or name == base:
                continue
            if name.endswith("." + base):
                found.add(name)
    return found


def probe_host(host: str, timeout: float = 3.0) -> dict:
    """
    بررسی زنده بودن: DNS resolution + TCP connect به 443.
    Returns: {domain, ip, alive, reason}
    """
    ip = resolve_host(host, timeout=timeout)
    if ip is None:
        return {"domain": host, "ip": None, "alive": False, "reason": "dns"}

    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return {"domain": host, "ip": ip, "alive": True, "reason": "tcp-ok"}
    except socket.timeout:
        return {"domain": host, "ip": ip, "alive": False, "reason": "tcp-timeout"}
    except ConnectionRefusedError:
        return {"domain": host, "ip": ip, "alive": False, "reason": "tcp-refused"}
    except Exception as e:
        return {"domain": host, "ip": ip, "alive": False, "reason": str(e)[:50]}


def probe_hosts_parallel(
    hosts: set[str] | list[str],
    max_workers: int = 20,
    timeout: float = 3.0,
    on_progress=None,
) -> list[dict]:
    """بررسی موازی. فقط hostهای زنده را (مرتب‌شده) برمی‌گرداند."""
    hosts = list(hosts)
    alive = []
    total = len(hosts)
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(probe_host, h, timeout): h for h in hosts}
        for future in as_completed(futures):
            done += 1
            try:
                r = future.result()
            except Exception:
                continue
            if on_progress:
                try:
                    on_progress(done, total, r["domain"])
                except Exception:
                    pass
            if r["alive"]:
                alive.append(r)

    return sorted(alive, key=lambda x: x["domain"])


def discover(
    base: str = "apibaz.org",
    max_n: int = 50,
    use_crtsh: bool = True,
    use_patterns: bool = True,
    use_wordlist: bool = True,
    extra_candidates: set[str] | None = None,
    known_domains: set[str] | None = None,
    max_workers: int = 20,
    probe_timeout: float = 3.0,
    on_progress=None,
) -> dict:
    """
    کشف زیردامنه‌های پنهان.

    Returns dict با کلیدها:
      - crtsh: set دامنه‌های یافته در CT logs
      - patterns: set کاندیدهای الگویی
      - words: set کاندیدهای واژه‌ای
      - alive: list دامنه‌های زنده [{domain, ip, reason}]
      - newly_discovered: list دامنه‌های زنده‌ای که در known نبودند
    """
    known_domains = known_domains or set()
    result = {
        "crtsh": set(),
        "patterns": set(),
        "words": set(),
        "alive": [],
        "newly_discovered": [],
    }

    # ۱. CT logs
    if use_crtsh:
        if on_progress:
            on_progress("crtsh", "در حال جستجو...", 0, 0)
        result["crtsh"] = query_crtsh(base)

    # ۲. کاندیدها
    candidates = set(result["crtsh"])

    if use_patterns:
        result["patterns"] = generate_pattern_candidates(base, max_n=max_n)
        candidates.update(result["patterns"])

    if use_wordlist:
        result["words"] = generate_word_candidates(base)
        candidates.update(result["words"])

    if extra_candidates:
        candidates.update(extra_candidates)

    # حذف known
    candidates -= known_domains

    # ۳. بررسی موازی
    if on_progress:
        on_progress("probe", f"بررسی {len(candidates)} کاندید...", 0, len(candidates))

    result["alive"] = probe_hosts_parallel(
        candidates, max_workers=max_workers, timeout=probe_timeout,
    )

    # ۴. جداسازی تازه‌ها
    result["newly_discovered"] = [
        item for item in result["alive"]
        if item["domain"] not in known_domains
    ]

    return result