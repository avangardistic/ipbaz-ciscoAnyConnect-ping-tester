"""
مدیریت جلسه‌ی openconnect با Context Manager (RAII).

سازگار با ویندوز 9.x:
- --background حذف شد.
- هش گواهی به‌طور خودکار کشف و کش می‌شود.
- پس از Configured as، DNS و metric روی tun adapter به‌صورت دستی اصلاح می‌شود.
- پشتیبانی از --script سفارشی (متغیر VPN_SCRIPT).
"""
from __future__ import annotations

import os
import platform
import re
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import win_net


class VPNError(Exception):
    """خطای اتصال یا مدیریت جلسه VPN."""


_CERT_HASH_CACHE: dict[str, str] = {}
_CERT_HASH_LOCK = threading.Lock()


def _get_cached_hash() -> str:
    with _CERT_HASH_LOCK:
        return _CERT_HASH_CACHE.get("apibaz", "")


def _set_cached_hash(h: str) -> None:
    if not h:
        return
    with _CERT_HASH_LOCK:
        _CERT_HASH_CACHE["apibaz"] = h


def _extract_cert_hash(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r'--servercert\s+(pin-sha256:[A-Za-z0-9+/=]+)', text)
    if m:
        return m.group(1)
    m = re.search(r'(pin-sha256:[A-Za-z0-9+/=]+)', text)
    return m.group(1) if m else None


def _kill_process(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    try:
        if process.poll() is None:
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(process.pid)],
                    capture_output=True, timeout=5, check=False,
                )
            else:
                process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
    except Exception:
        pass


def _start_openconnect(
    domain: str,
    username: str,
    password: str,
    cert_hash: str,
    log_path: Path,
    script_path: str = "",
    settle_time: float = 1.5,
    pid_file: Path | None = None,
) -> tuple[subprocess.Popen | None, str]:
    cmd = [
        "openconnect",
        f"--user={username}",
        "--passwd-on-stdin",
        "--non-inter",
    ]
    if cert_hash:
        cmd.extend(["--servercert", cert_hash])
    else:
        cmd.append("--no-cert-check")
    if script_path:
        cmd.extend(["--script", script_path])
    cmd.append(domain)

    creationflags = (
        subprocess.CREATE_NEW_PROCESS_GROUP
        if platform.system() == "Windows"
        else 0
    )

    try:
        log_fh = open(log_path, "w", encoding="utf-8", errors="replace")
    except OSError as e:
        return None, f"نمی‌توان فایل لاگ را باز کرد: {e}"

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        log_fh.close()
        return None, "openconnect در PATH یافت نشد"

    try:
        process.stdin.write(password + "\n")
        process.stdin.flush()
    except (BrokenPipeError, OSError):
        pass

    deadline = time.monotonic() + settle_time
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_fh.close()
            try:
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                log_text = ""
            return None, log_text
        time.sleep(0.2)

    if pid_file is not None:
        try:
            pid_file.write_text(str(process.pid))
        except OSError:
            pass

    return process, ""


def _wait_for_tunnel_ready(
    log_path: Path,
    max_wait: float = 20.0,
    initial_wait: float = 1.0,
) -> tuple[bool, str]:
    """منتظر 'Configured as' در لاگ می‌ماند."""
    deadline = time.monotonic() + max_wait
    time.sleep(initial_wait)
    while time.monotonic() < deadline:
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        lowered = text.lower()
        if "configured as" in lowered:
            return True, "vpnc-script اجرا شد"
        if "failed to complete authentication" in lowered:
            return False, "احراز هویت شکست خورد"
        if "failed to" in lowered and "configure" in lowered:
            return False, "vpnc-script خطا داد"
        time.sleep(0.5)
    return False, "زمان انتظار برای Configured as تمام شد"


def _fix_windows_tunnel(domain: str = "") -> tuple[bool, str]:
    """پس از Configured as، adapter را پیدا و DNS/metric/route را اصلاح می‌کند."""
    if not win_net.is_windows():
        return True, "skip (non-windows)"

    # تا ۱۵ ثانیه صبر برای ظاهر شدن adapter (با hint دامنه)
    adapter = None
    for _ in range(30):
        adapter = win_net.find_tun_adapter(domain_hint=domain)
        if adapter:
            break
        time.sleep(0.5)

    if not adapter:
        return False, "tun adapter در ۱۵ ثانیه پیدا نشد"

    ok, msg = win_net.fix_tunnel_network(adapter)
    return ok, f"adapter='{adapter}' {msg}"


def _connect_with_retry(
    domain: str,
    username: str,
    password: str,
    cert_hash: str,
    log_path: Path,
    script_path: str,
    settle_time: float,
    pid_file: Path,
) -> subprocess.Popen:
    effective = cert_hash or _get_cached_hash()

    process, log_text = _start_openconnect(
        domain, username, password, effective,
        log_path=log_path, script_path=script_path,
        settle_time=settle_time, pid_file=pid_file,
    )
    if process is not None:
        return process

    if not effective:
        extracted = _extract_cert_hash(log_text)
        if extracted:
            _set_cached_hash(extracted)
            pid_file.unlink(missing_ok=True)
            log_path.write_text("", encoding="utf-8")
            process, log_text = _start_openconnect(
                domain, username, password, extracted,
                log_path=log_path, script_path=script_path,
                settle_time=settle_time, pid_file=pid_file,
            )
            if process is not None:
                return process

    last = log_text.strip().splitlines()[-1] if log_text.strip() else "بدون جزئیات"
    raise VPNError(f"openconnect شکست خورد: {last[:300]}")


@contextmanager
def _append_log(log_path: Path, msg: str) -> None:
    """الحاق به لاگ با مدیریت خطای فایل ناموجود."""
    try:
        existing = log_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        existing = ""
    except OSError:
        return
    try:
        log_path.write_text(existing + msg, encoding="utf-8")
    except OSError:
        pass


@contextmanager
def openconnect_session(
    domain: str,
    username: str,
    password: str,
    cert_hash: str = "",
    script_path: str = "",
    connect_timeout: int = 35,
    settle_time: float = 1.5,
    wait_tunnel_ready: bool = True,
    tunnel_ready_timeout: float = 20.0,
    pid_dir: Path | None = None,
) -> Iterator[int]:
    pid_dir = pid_dir or Path.cwd()
    pid_dir.mkdir(parents=True, exist_ok=True)
    safe_domain = domain.replace(".", "_").replace(":", "_")
    pid_file = pid_dir / f".openconnect_{safe_domain}.pid"
    log_path = pid_dir / f".openconnect_{safe_domain}.log"
    pid_file.unlink(missing_ok=True)

    process: subprocess.Popen | None = None
    try:
        process = _connect_with_retry(
            domain, username, password, cert_hash,
            log_path=log_path, script_path=script_path,
            settle_time=settle_time, pid_file=pid_file,
        )

        if wait_tunnel_ready:
            ready, reason = _wait_for_tunnel_ready(
                log_path, max_wait=tunnel_ready_timeout,
            )
            if not ready:
                raise VPNError(f"تونل آماده نشد: {reason} (لاگ: {log_path.name})")

            ok, fix_msg = _fix_windows_tunnel(domain)  # ← domain پاس می‌شود
            if not ok:
                _append_log(log_path, f"\n[NETFIX-SKIP] {fix_msg}\n")  # ← SKIP نه FAIL
            else:
                _append_log(log_path, f"\n[NETFIX-OK] {fix_msg}\n")

        yield process.pid
    finally:
        _kill_process(process)
        pid_file.unlink(missing_ok=True)

def test_session_tunnel_ready_but_fix_fails_still_returns(tmp_path):
    """اگر _fix_windows_tunnel شکست بخورد، جلسه ادامه می‌یابد و در لاگ ثبت می‌شود."""
    fake = _fake_proc()
    with patch.object(vpn, "_start_openconnect", return_value=(fake, "")), \
         patch.object(vpn, "_kill_process"), \
         patch.object(vpn, "_wait_for_tunnel_ready", return_value=(True, "ok")), \
         patch.object(vpn, "_fix_windows_tunnel",
                      return_value=(False, "tun adapter پیدا نشد")):
        with vpn.openconnect_session(
            "d.com", "u", "p", pid_dir=tmp_path, wait_tunnel_ready=True,
        ) as pid:
            assert pid == 1234

    # فایل لاگ باید با پیام NETFIX-FAIL ایجاد شده باشد
    log_files = list(tmp_path.glob(".openconnect_*.log"))
    assert log_files, "فایل لاگ ایجاد نشد"
    content = log_files[0].read_text(encoding="utf-8")
    assert "NETFIX-FAIL" in content
    assert "tun adapter پیدا نشد" in content