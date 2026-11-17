"""رابط خط فرمان: test + discover + add-domain."""
from __future__ import annotations

import argparse
import datetime
import json
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from .config import (
    ConfigError,
    DEFAULT_DOMAINS,
    DOMAINS_FILE,
    load_config,
    load_domains_file,
    save_domains_file,
)
from .runner import TestResult, run_all


# ---------- پیش‌بررسی‌ها ----------

def _require_admin() -> bool:
    if platform.system() == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        import os
        return os.geteuid() == 0
    except AttributeError:
        return True


def _check_openconnect_installed() -> bool:
    try:
        return subprocess.run(
            ["openconnect", "--version"],
            capture_output=True, timeout=5, check=False,
        ).returncode == 0
    except (FileNotFoundError, Exception):
        return False


# ---------- نمایش نتایج تست ----------

def _print_result(idx: int, total: int, r: TestResult) -> None:
    icons = {"youtube_ok": "✅", "vpn_only": "🔒", "dns_ok": "⚠️ ", "unreachable": "❌"}
    icon = icons.get(r.status, "?")
    print(f"[{idx:>2}/{total}] {icon} {r.domain:<22} ({r.elapsed:5.1f}s) - {r.detail}")


def _print_summary(results: list[TestResult], output_path: Path, best_path: Path) -> None:
    ok = [r for r in results if r.youtube_ok]
    total = len(results)

    print("\n" + "=" * 72)
    print(f"  ✅ YouTube از {len(ok)}/{total} سرور قابل دسترسی است")
    print("=" * 72)

    if ok:
        for r in sorted(ok, key=lambda r: r.elapsed):
            print(f"   • {r.domain:<22} ({r.elapsed:5.1f}s, egress={r.egress_ip})")
    else:
        print("\n❌ هیچ سروری YouTube را باز نکرد.\n")

    print(f"\n📄 نتایج کامل:   {output_path}")
    print(f"📌 بهترین سرورها: {best_path}")


def _write_best_servers(path: Path, results: list[TestResult]) -> None:
    ok = sorted([r for r in results if r.youtube_ok], key=lambda r: r.elapsed)
    lines = [
        "# بهترین سرورهای Cisco AnyConnect (به ترتیب سرعت)",
        f"# تاریخ: {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"# موفق: {len(ok)}/{len(results)}",
        "",
    ]
    if ok:
        for i, r in enumerate(ok, start=1):
            lines.append(f"{i:>2}. {r.domain:<22}  {r.elapsed:5.1f}s  egress={r.egress_ip}")
    else:
        lines.append("# هیچ سرور موفقی یافت نشد")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8-sig")


# ---------- command: test (پیش‌فرض) ----------

def build_test_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vpn-tester",
        description="تست دسترسی به YouTube از طریق سرورهای Cisco AnyConnect",
        epilog="زیردستورهای دیگر: discover (کشف زیردامنه), add-domain (افزودن دستی)",
    )
    p.add_argument("--output", default="results.json", help="مسیر فایل JSON")
    p.add_argument("--best", default="best_servers.txt", help="مسیر فایل بهترین سرورها")
    p.add_argument("--domain", action="append", default=None, help="فقط این دامنه(ها)")
    p.add_argument("--retries", type=int, default=None, help="تلاش مجدد")
    p.add_argument("--skip-precheck", action="store_true", help="رد کردن پیش‌بررسی")
    return p


def test_main(argv: list[str]) -> int:
    args = build_test_parser().parse_args(argv)

    if not args.skip_precheck:
        if not _check_openconnect_installed():
            print("[خطا] openconnect در PATH یافت نشد.", file=sys.stderr)
            return 2
        if not _require_admin():
            print("[خطا] نیاز به دسترسی Administrator/root دارد.", file=sys.stderr)
            return 2

    try:
        config = load_config(require_credentials=True)
    except ConfigError as exc:
        print(f"[خطا پیکربندی] {exc}", file=sys.stderr)
        return 3

    overrides: dict = {}
    if args.domain:
        overrides["domains"] = tuple(args.domain)
    if args.retries is not None:
        overrides["retries"] = args.retries
    if overrides:
        config = replace(config, **overrides)

    results = run_all(config, on_progress=_print_result)

    output_path = Path(args.output).resolve()
    payload = {
        "generated_at": datetime.datetime.now().isoformat(),
        "username": config.username,
        "total": len(results),
        "youtube_ok": sum(1 for r in results if r.youtube_ok),
        "results": [r.to_dict() for r in results],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )

    best_path = Path(args.best).resolve()
    _write_best_servers(best_path, results)
    _print_summary(results, output_path, best_path)

    return 0 if payload["youtube_ok"] > 0 else 1


# ---------- command: discover ----------

def build_discover_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vpn-tester discover",
        description="کشف زیردامنه‌های پنهان apibaz.org (یا هر دامنه)",
    )
    p.add_argument("--base", default="apibaz.org", help="دامنه‌ی پایه")
    p.add_argument("--max-n", type=int, default=50, help="حداکثر عدد در الگوها")
    p.add_argument("--workers", type=int, default=20, help="تعداد worker موازی")
    p.add_argument("--timeout", type=float, default=3.0, help="timeout هر probe (ثانیه)")
    p.add_argument("--no-crtsh", action="store_true", help="غیرفعال crt.sh")
    p.add_argument("--no-patterns", action="store_true", help="غیرفعال الگوها")
    p.add_argument("--no-wordlist", action="store_true", help="غیرفعال واژه‌ها")
    p.add_argument("--save", action="store_true", help="ذخیره در domains.txt")
    p.add_argument("--overwrite", action="store_true",
                   help="بازنویسی domains.txt (بدون پیش‌فرض‌ها)")
    p.add_argument("--add", action="append", default=None,
                   help="افزودن دستی دامنه (بدون کشف)")
    p.add_argument("--output", default="discovered.json", help="مسیر خروجی JSON")
    return p


def discover_main(argv: list[str]) -> int:
    args = build_discover_parser().parse_args(argv)

    # ---------- حالت --add: فقط افزودن دستی ----------
    if args.add:
        current = [] if args.overwrite else (
            load_domains_file(DOMAINS_FILE) or list(DEFAULT_DOMAINS)
        )
        merged = list(dict.fromkeys(current + args.add))
        save_domains_file(DOMAINS_FILE, merged)
        print(f"✓ {len(args.add)} دامنه اضافه شد به {DOMAINS_FILE}")
        print(f"  کل: {len(merged)} دامنه")
        return 0

    # ---------- حالت کشف ----------
    from .discovery import discover

    print("=" * 64)
    print(f"  🔍 کشف زیردامنه‌های {args.base}")
    print("=" * 64)

    def progress(phase: str, msg: str, done: int, total: int):
        if phase == "crtsh":
            print(f"  [crt.sh] {msg}")
        elif phase == "probe" and total > 0:
            pct = int(100 * done / total) if total > 0 else 0
            print(f"\r  [probe] {done}/{total} ({pct}%)  ", end="", flush=True)

    result = discover(
        base=args.base,
        max_n=args.max_n,
        use_crtsh=not args.no_crtsh,
        use_patterns=not args.no_patterns,
        use_wordlist=not args.no_wordlist,
        known_domains=set(DEFAULT_DOMAINS),
        max_workers=args.workers,
        probe_timeout=args.timeout,
        on_progress=progress,
    )
    print()

    # ---------- خلاصه ----------
    print("=" * 64)
    print("  📊 کشف تمام شد")
    print("=" * 64)
    print(f"  crt.sh:       {len(result['crtsh']):>5} دامنه")
    print(f"  الگوها:       {len(result['patterns']):>5} کاندید")
    print(f"  واژه‌ها:       {len(result['words']):>5} کاندید")
    print(f"  زنده:         {len(result['alive']):>5} دامنه")
    print(f"  تازه:         {len(result['newly_discovered']):>5} دامنه")
    print()

    if result["newly_discovered"]:
        print("🎉 دامنه‌های تازه کشف‌شده:")
        for item in result["newly_discovered"]:
            print(f"   • {item['domain']:<30} → {item['ip']}")
    elif result["alive"]:
        print("ℹ️  همه‌ی دامنه‌های زنده از قبل شناخته‌شده بودند.")
    else:
        print("❌ هیچ دامنه‌ی زنده‌ای یافت نشد.")

    # ---------- ذخیره JSON ----------
    output_path = Path(args.output).resolve()
    payload = {
        "generated_at": datetime.datetime.now().isoformat(),
        "base": args.base,
        "crtsh": sorted(result["crtsh"]),
        "alive": result["alive"],
        "newly_discovered": result["newly_discovered"],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )
    print(f"\n📄 نتایج کامل: {output_path}")

    # ---------- ذخیره در domains.txt ----------
    if args.save and result["alive"]:
        current = [] if args.overwrite else (
            load_domains_file(DOMAINS_FILE) or list(DEFAULT_DOMAINS)
        )
        new_domains = [item["domain"] for item in result["alive"]]
        merged = list(dict.fromkeys(current + new_domains))
        save_domains_file(DOMAINS_FILE, merged)
        print(f"💾 ذخیره در {DOMAINS_FILE} ({len(merged)} دامنه)")
        print(f"   اجرای بعدی: python run.py (از domains.txt می‌خواند)")

    return 0 if result["alive"] else 1


# ---------- dispatcher ----------

def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]

    if argv and argv[0] == "discover":
        return discover_main(argv[1:])

    if argv and argv[0] == "add-domain":
        # transform: add-domain a.com b.com → --add a.com --add b.com
        new_argv: list[str] = []
        for d in argv[1:]:
            new_argv.extend(["--add", d])
        return discover_main(new_argv)

    return test_main(argv)