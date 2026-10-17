"""ورودی خط فرمانِ پل.

پیام‌های این پنجره عمداً **انگلیسی و ASCII** هستند: کنسول ویندوز متن
راست‌به‌چپ را وارونه و بریده نشان می‌دهد و یک بار همین کار را از دست
صاحب فروشگاه درآورد. متن فارسی فقط داخل JSON می‌رود، که مرورگر درست
نشانش می‌دهد.

  iPhoneBridge.exe            سرور را بالا می‌آورد (کار همیشگی)
  iPhoneBridge.exe read       یک بار می‌خواند و JSON چاپ می‌کند
  iPhoneBridge.exe selftest   بدون گوشی، خودش را می‌سنجد
  iPhoneBridge.exe --pos-server URL --pos-token رمز   همراهِ آیفون، مبلغ را به کارتخوان هم می‌رساند (`pos/`)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading
import urllib.error
import urllib.request

from . import __version__
from .console import say
from .device import now_iso, read_device
from .errors import BridgeError
from .server import DEFAULT_ORIGINS, DEFAULT_PORT, PROTOCOL, make_server, serve


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iPhoneBridge",
        description="Reads the connected iPhone and serves it on 127.0.0.1 for the accounting web app.",
    )
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "read", "selftest"])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default {DEFAULT_PORT}")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="extra web page allowed to read the phone, e.g. https://panel.example.com",
    )
    parser.add_argument("--pos-server", metavar="URL", help="accounting server for card-reader payments, e.g. https://novo.stland.ir")
    parser.add_argument("--pos-token", metavar="TOKEN", help="bridge token from the card-reader page")
    parser.add_argument("--version", action="version", version=f"iPhoneBridge {__version__}")
    return parser


def _origins(extra: list[str]) -> tuple[str, ...]:
    seen: list[str] = list(DEFAULT_ORIGINS)
    for origin in extra:
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return tuple(seen)


def _read_once() -> int:
    try:
        device = asyncio.run(read_device())
        payload = {"ok": True, "readAt": now_iso(), "device": device}
        code = 0
    except BridgeError as err:
        payload = err.to_dict()
        code = 1
    # ensure_ascii عمدی است: کنسول ویندوز cp1252 است و فارسی خامْ
    # کل برنامه را می‌اندازد. \uXXXX هم JSON معتبر است.
    say(json.dumps(payload, ensure_ascii=True, indent=2))
    return code


def _get(url: str, origin: str | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url)
    if origin:
        request.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def _selftest() -> int:
    """بدون آیفون، ثابت می‌کند که خودِ فایل اجرایی سالم است.

    این همان چیزی است که در CI روی ویندوز اجرا می‌شود: اگر PyInstaller
    ماژولی را جا انداخته باشد، اینجا معلوم می‌شود نه روی کامپیوتر
    فروشگاه.
    """
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        say(f"  {'ok  ' if condition else 'FAIL'}  {name}{'' if condition else f'  ({detail})'}")
        if not condition:
            failures.append(name)

    say(f"iPhone Bridge {__version__} self-test  ({sys.platform}, frozen={getattr(sys, 'frozen', False)})")

    # کتابخانه‌ها واقعاً داخل فایل اجرایی هستند؟
    #
    # هر ماژول **جداگانه** ایمپورت می‌شود و در صورت شکست، ردِ کامل خطا
    # چاپ می‌شود. یک بار همین‌جا فقط «ImportError» دیدیم و معلوم نبود
    # کدام ماژول و چرا — و یک دور کاملِ CI برای فهمیدنش رفت.
    #
    # `osu.os_utils` عمداً در فهرست است: روی ویندوز خودِ کتابخانه هنگام
    # ایمپورت `lockdown` سراغش می‌رود و آن هم `win32security` را می‌خواهد،
    # که اگر PyInstaller جا بیندازدش تازه روی کامپیوتر فروشگاه معلوم
    # می‌شد.
    missing = False
    for module, attr in (
        ("pymobiledevice3.irecv_devices", "IRECV_DEVICES"),
        ("pymobiledevice3.osu.os_utils", "get_os_utils"),
        ("pymobiledevice3.lockdown", "create_using_usbmux"),
        ("pymobiledevice3.services.diagnostics", "DiagnosticsService"),
    ):
        try:
            imported = __import__(module, fromlist=[attr])
            getattr(imported, attr)
            check(f"{module} is bundled", True)
        except BaseException as exc:  # noqa: BLE001 - می‌خواهیم هر چیزی را ببینیم
            import traceback

            check(f"{module} is bundled", False, f"{type(exc).__name__}: {exc}")
            for line in traceback.format_exc().splitlines():
                say(f"        {line}")
            missing = True

    if not missing:
        # ساختنِ OsUtils همان کاری است که کتابخانه در زمان اجرا می‌کند
        try:
            from pymobiledevice3.osu.os_utils import get_os_utils

            check("platform helper builds", get_os_utils() is not None)
        except BaseException as exc:  # noqa: BLE001
            import traceback

            check("platform helper builds", False, f"{type(exc).__name__}: {exc}")
            for line in traceback.format_exc().splitlines():
                say(f"        {line}")
            missing = True

    if missing:
        say("")
        say("The executable is missing part of pymobiledevice3. Check iPhoneBridge.spec.")
        return 1

    from .marketing import marketing_capacity_gb, marketing_name

    check("marketing names load", marketing_name("iPhone18,2") == "iPhone 17 Pro Max",
          repr(marketing_name("iPhone18,2")))
    check("capacity maths", marketing_capacity_gb(251_000_000_000) == 256)

    # سرور روی پورت آزاد (۰ یعنی سیستم خودش انتخاب کند)
    httpd = make_server(0, (*DEFAULT_ORIGINS, "https://selftest.example"), quiet=True)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        status, health = _get(f"{base}/health")
        check("health answers", status == 200 and health.get("protocol") == PROTOCOL, repr(health))

        status, _ = _get(f"{base}/health", origin="https://selftest.example")
        check("allowed page may read", status == 200)

        status, _ = _get(f"{base}/health", origin="https://attacker.example")
        check("other pages are refused", status == 403, f"status {status}")

        # بدون گوشی باید پیام روشن بدهد، نه بترکد
        status, body = _get(f"{base}/device")
        clear = status == 200 and body.get("ok") is False and bool(body.get("error"))
        check("no phone gives a clear message", clear, repr(body))
        if clear:
            say(f"        code={body.get('code')}")
    finally:
        httpd.shutdown()
        httpd.server_close()

    if failures:
        say("")
        say(f"{len(failures)} check(s) failed.")
        return 1
    say("")
    say("All checks passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "read":
        return _read_once()
    if args.command == "selftest":
        return _selftest()
    if args.pos_server and args.pos_token:
        # ارسالِ مبلغ به کارتخوان کنارِ سرورِ آیفون، در نخِ خودش (`pos/agent.py`)
        from .pos import run_agent_thread

        run_agent_thread(args.pos_server, args.pos_token)
    serve(args.port, _origins(args.allow))
    return 0


if __name__ == "__main__":
    sys.exit(main())
