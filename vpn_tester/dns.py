"""حل DNS با timeout (چون socket.getaddrinfo پارامتر timeout ندارد)."""
from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout


def resolve_host(host: str, timeout: float = 5.0) -> str | None:
    """
    حل یک دامنه به IPv4.

    Args:
        host: دامنه برای resolve.
        timeout: حداکثر زمان انتظار به ثانیه.

    Returns:
        آدرس IPv4 یا None در صورت شکست/timeout.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(socket.gethostbyname, host)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            return None
        except (socket.gaierror, OSError):
            return None