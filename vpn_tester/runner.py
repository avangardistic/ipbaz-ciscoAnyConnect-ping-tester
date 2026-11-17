"""ارکستراتور تست دامنه‌ها با تلاش مجدد اختیاری."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from .config import Config
from .dns import resolve_host
from .vpn import VPNError, openconnect_session
from . import youtube


@dataclass
class TestResult:
    """نتیجه‌ی تست یک دامنه."""

    domain: str
    dns_ok: bool
    vpn_ok: bool
    youtube_ok: bool
    detail: str
    elapsed: float
    egress_ip: str | None = None
    interpretation: str = ""

    @property
    def status(self) -> str:
        if self.youtube_ok:
            return "youtube_ok"
        if self.vpn_ok:
            return "vpn_only"
        if self.dns_ok:
            return "dns_ok"
        return "unreachable"

    def to_dict(self) -> dict:
        """سریالایز شامل status (که property است و در asdict نمی‌آید)."""
        d = asdict(self)
        d["status"] = self.status
        return d


def _test_domain_once(domain: str, config: Config) -> TestResult:
    """یک تلاش کامل برای تست یک دامنه (بدون retry)."""
    start = time.monotonic()

    # مرحله ۱: DNS
    ip = resolve_host(domain)
    if ip is None:
        return TestResult(
            domain=domain, dns_ok=False, vpn_ok=False, youtube_ok=False,
            detail="دامنه resolve نشد",
            elapsed=time.monotonic() - start,
            interpretation="DNS مسدود — دامنه resolve نشد",
        )

    # مرحله ۲: VPN + انتظار برای Configured as
    try:
        with openconnect_session(
            domain=domain,
            username=config.username,
            password=config.password,
            cert_hash=config.cert_hash,
            script_path=config.script_path,
            connect_timeout=config.connect_timeout,
            settle_time=1.5,
            wait_tunnel_ready=True,
            tunnel_ready_timeout=20.0,
            pid_dir=config.pid_dir,
        ) as pid:
            # فرصت برای propagat شدن DNS در کش ویندوز
            time.sleep(1.5)

            # مرحله ۳: تشخیص YouTube
            diag = youtube.diagnose(timeout=config.youtube_timeout)

            parts = [
                f"IP={ip}",
                f"PID={pid}",
                f"DNS:{'✓' if diag['dns_ok'] else '✗'}",
                f"TCP:{'✓' if diag['tcp_ok'] else '✗'}",
                f"HTTP:{'✓' if diag['http_ok'] else '✗'}",
            ]
            if diag["egress_ip"]:
                parts.append(f"egress={diag['egress_ip']}")
            detail = " | ".join(parts)

            return TestResult(
                domain=domain,
                dns_ok=True,
                vpn_ok=True,
                youtube_ok=diag["youtube_ok"],
                detail=detail,
                elapsed=time.monotonic() - start,
                egress_ip=diag["egress_ip"],
                interpretation=diag["interpretation"],
            )
    except VPNError as exc:
        return TestResult(
            domain=domain, dns_ok=True, vpn_ok=False, youtube_ok=False,
            detail=f"IP={ip} | {exc}",
            elapsed=time.monotonic() - start,
            interpretation=str(exc),
        )


def test_domain(
    domain: str,
    config: Config,
    retries: int = 0,
    retry_delay: float = 2.0,
) -> TestResult:
    """
    اجرای تست با تلاش مجدد خودکار.

    Retry در این موارد رخ نمی‌دهد:
      - DNS شکست خورده (احتمالاً دائمی)
      - آخرین تلاش

    retries: تعداد تلاش‌های اضافی پس از اولین شکست (0 = بدون retry).
    """
    result: TestResult | None = None

    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(retry_delay)

        result = _test_domain_once(domain, config)

        if result.youtube_ok:
            # موفق — نیازی به تلاش بیشتر نیست
            if attempt > 0:
                result.detail += f" [attempt {attempt + 1}]"
            return result

        if not result.dns_ok:
            # DNS مسدود — retry بی‌فایده است
            return result

    # همه‌ی تلاش‌ها شکست خوردند
    assert result is not None
    if retries > 0:
        result.detail += f" [after {retries + 1} attempts]"
    return result


def run_all(config: Config, on_progress=None) -> list[TestResult]:
    """
    تست ترتیبی همه‌ی دامنه‌ها.

    ترتیبی اجرا می‌شود چون هر اتصال openconnect یک tun می‌سازد و
    روی routing table سیستم اثر می‌گذارد.
    """
    results: list[TestResult] = []
    total = len(config.domains)

    for idx, domain in enumerate(config.domains, start=1):
        result = test_domain(domain, config, retries=config.retries)
        results.append(result)

        if on_progress:
            on_progress(idx, total, result)

        if idx < total:
            time.sleep(config.between_tests_delay)

    return results