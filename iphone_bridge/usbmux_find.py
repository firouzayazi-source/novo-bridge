"""پیدا کردنِ سرویسِ اپل (usbmuxd) روی ویندوز.

pymobiledevice3 روی ویندوز فقط `127.0.0.1:27015` را امتحان می‌کند — درگاهِ iTunesِ قدیمی. صاحب فروشگاه (۲۸ مهر ۱۴۰۵):
«گوشی رو نمی‌شناسه» — برنامه‌ی «Apple Devices» گوشی را می‌دید و پیغامِ Trust می‌داد، ولی پل می‌گفت «سرویس اپل اجرا
نیست». یعنی سرویس بود، فقط جای دیگری گوش می‌داد یا هنوز بالا نیامده بود.

پس پیش از هر خواندن:
• اگر `USBMUXD_SOCKET_ADDRESS` را کسی داده، همان (قراردادِ خودِ libusbmuxd).
• اگر ۲۷۰۱۵ باز است، کاری نمی‌کنیم.
• وگرنه درگاه‌هایی که برنامه‌ی اپلی (`AppleMobileDevice…`، `usbmuxd`) روی لوپ‌بک گوش می‌دهد از `netstat` خوانده و
  یکی‌یکی امتحان می‌شود؛ اولی که جواب داد در همان متغیر می‌نشیند و pymobiledevice3 از آن می‌خواند.

اگر هیچ‌کدام نشد، `diagnose()` می‌گوید چرا — برنامه‌ی اپل اصلاً نیست، یا هست ولی گوش نمی‌دهد — تا پیامِ کاربر
راهِ درست را بگوید.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass

ENV = "USBMUXD_SOCKET_ADDRESS"
DEFAULT_PORT = 27015

#: نامِ فرایندهایی که سرویسِ اپل را دارند — iTunesِ قدیمی، «Apple Devices»ِ فروشگاهِ مایکروسافت، و usbmuxdِ جدا
APPLE_PROCESS = re.compile(r"apple\s*mobile\s*device|usbmuxd", re.IGNORECASE)

#: نشانی‌ای که خودمان در متغیر گذاشتیم — اگر سرویس جابه‌جا شد، فراموشش می‌کنیم و از نو می‌گردیم
_ours: str | None = None


@dataclass(frozen=True)
class Diagnosis:
    """آنچه درباره‌ی سرویسِ اپل روی این کامپیوتر می‌دانیم."""

    address: str | None
    """نشانی‌ای که جواب داد؛ `None` یعنی هیچ‌کدام"""
    apple_processes: tuple[str, ...]
    """نامِ فرایندهای اپلیِ در حالِ اجرا"""
    tried: tuple[str, ...]

    def detail(self) -> str:
        procs = ", ".join(self.apple_processes) or "none"
        return f"tried {', '.join(self.tried) or '-'}; apple processes: {procs}"


def _open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_netstat(text: str) -> list[tuple[str, int, int]]:
    """خروجیِ `netstat -ano -p TCP` ← (نشانی، درگاه، شناسه‌ی فرایند) برای خط‌های LISTENING."""
    out: list[tuple[str, int, int]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        host, _, port = parts[1].rpartition(":")
        if not port.isdigit() or not parts[4].isdigit():
            continue
        out.append((host, int(port), int(parts[4])))
    return out


def parse_tasklist(text: str) -> dict[int, str]:
    """خروجیِ `tasklist /FO CSV /NH` ← شناسه‌ی فرایند به نام."""
    out: dict[int, str] = {}
    for line in text.splitlines():
        cells = [c.strip().strip('"') for c in line.split('","')]
        if len(cells) >= 2 and cells[1].strip('"').isdigit():
            out[int(cells[1].strip('"'))] = cells[0].strip('"')
    return out


def apple_ports(netstat: str, tasklist: str) -> tuple[list[int], list[str]]:
    """درگاه‌های لوپ‌بکی که فرایندِ اپلی گوش می‌دهد، و نامِ همان فرایندها."""
    names = parse_tasklist(tasklist)
    apple = {pid: name for pid, name in names.items() if APPLE_PROCESS.search(name)}
    ports: list[int] = []
    for host, port, pid in parse_netstat(netstat):
        if pid in apple and host in {"127.0.0.1", "0.0.0.0", "[::1]", "[::]"} and port not in ports:
            ports.append(port)
    return ports, sorted(set(apple.values()))


def _run(args: list[str]) -> str:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=5, creationflags=flags).stdout or ""
    except Exception:
        return ""


def diagnose() -> Diagnosis:
    """سرویس را پیدا می‌کند و اگر جای دیگری بود، متغیرِ محیطی را می‌گذارد."""
    global _ours
    given = os.environ.get(ENV)
    if given and given == _ours:
        host, _, port = given.rpartition(":")
        if _open(host, int(port)):
            return Diagnosis(given, (), (given,))
        del os.environ[ENV]
        _ours = given = None
    if given:
        host, _, port = given.rpartition(":")
        ok = port.isdigit() and _open(host or "127.0.0.1", int(port))
        return Diagnosis(given if ok else None, (), (given,))
    tried = [f"127.0.0.1:{DEFAULT_PORT}"]
    if _open("127.0.0.1", DEFAULT_PORT):
        return Diagnosis(tried[0], (), tuple(tried))
    if sys.platform != "win32":
        return Diagnosis(None, (), tuple(tried))
    ports, procs = apple_ports(_run(["netstat", "-ano", "-p", "TCP"]), _run(["tasklist", "/FO", "CSV", "/NH"]))
    for port in ports:
        address = f"127.0.0.1:{port}"
        tried.append(address)
        if port != DEFAULT_PORT and _open("127.0.0.1", port):
            os.environ[ENV] = _ours = address
            return Diagnosis(address, tuple(procs), tuple(tried))
    return Diagnosis(None, tuple(procs), tuple(tried))
