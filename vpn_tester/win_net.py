"""Windows network helpers: fix tun adapter DNS/metric/default route."""
from __future__ import annotations

import platform
import subprocess


def _run_ps(cmd: str, timeout: int = 20) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def find_tun_adapter(domain_hint: str = "") -> str | None:
    """
    پیدا کردن adapter با چند استراتژی (به ترتیب اولویت):
      1. تطبیق InterfaceDescription (Wintun/TAP/...)
      2. تطبیق Name با نام دامنه (مثلاً mcis1.apibaz.org)
      3. تطبیق Name با هر نامی که شامل 'apibaz' است
    """
    # 1. By description
    rc, out, _ = _run_ps(
        "Get-NetAdapter -ErrorAction SilentlyContinue | "
        "Where-Object { $_.InterfaceDescription -match "
        "'Wintun|TAP|OpenVPN|WireGuard|AnyConnect' } | "
        "Select-Object -First 1 -ExpandProperty Name"
    )
    if rc == 0 and out:
        return out.splitlines()[0].strip()

    # 2. By domain hint (اولین بخش دامنه)
    if domain_hint:
        short = domain_hint.split(".")[0]  # mcis1
        rc, out, _ = _run_ps(
            f"Get-NetAdapter -ErrorAction SilentlyContinue | "
            f"Where-Object {{ $_.Name -like '*{short}*' }} | "
            f"Select-Object -First 1 -ExpandProperty Name"
        )
        if rc == 0 and out:
            return out.splitlines()[0].strip()

    # 3. By 'apibaz' in name
    rc, out, _ = _run_ps(
        "Get-NetAdapter -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Name -like '*apibaz*' } | "
        "Select-Object -First 1 -ExpandProperty Name"
    )
    if rc == 0 and out:
        return out.splitlines()[0].strip()

    return None


def has_default_route(adapter_name: str) -> bool:
    rc, out, _ = _run_ps(
        f"@(Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
        f"-InterfaceAlias '{adapter_name}' -ErrorAction SilentlyContinue).Count"
    )
    return rc == 0 and out.strip().isdigit() and int(out.strip()) > 0


def add_default_route(adapter_name: str, metric: int = 1) -> tuple[bool, str]:
    rc, out, err = _run_ps(
        f"New-NetRoute -DestinationPrefix '0.0.0.0/0' "
        f"-InterfaceAlias '{adapter_name}' "
        f"-NextHop '0.0.0.0' -RouteMetric {metric} -ErrorAction Stop"
    )
    if rc != 0:
        return False, err or out
    return True, "default route added"


def fix_tunnel_network(
    adapter_name: str,
    dns_servers: list[str] | None = None,
    add_route: bool = True,
) -> tuple[bool, str]:
    dns = dns_servers or ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
    dns_str = ",".join(f"'{s}'" for s in dns)
    actions: list[str] = []

    rc, _, err = _run_ps(
        f"Set-NetIPInterface -InterfaceAlias '{adapter_name}' "
        f"-InterfaceMetric 1 -ErrorAction Stop"
    )
    if rc != 0:
        return False, f"metric: {err}"
    actions.append("metric=1")

    rc, _, err = _run_ps(
        f"Set-DnsClientServerAddress -InterfaceAlias '{adapter_name}' "
        f"-ServerAddresses @({dns_str}) -ErrorAction Stop"
    )
    if rc != 0:
        return False, f"dns: {err}"
    actions.append(f"dns={dns_str}")

    if add_route:
        if has_default_route(adapter_name):
            actions.append("default_route=exists")
        else:
            ok, msg = add_default_route(adapter_name, metric=1)
            if not ok:
                return False, f"route: {msg}"
            actions.append("default_route=added")

    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
    except Exception:
        pass

    return True, " ".join(actions)


def is_windows() -> bool:
    return platform.system() == "Windows"