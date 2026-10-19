"""سرور محلیِ پل — فقط روی ۱۲۷.۰.۰.۱.

مرورگرها `http://127.0.0.1` را از قاعده‌ی «محتوای ناامن» استثنا کرده‌اند،
پس پنلِ روی https می‌تواند از پلِ روی همین کامپیوتر بخواند بی‌آنکه
گواهی یا تونل یا سرور بیرونی لازم باشد.

─── چرا فهرست مبدأ لازم است ───

پل روی لوپ‌بک است، ولی «لوپ‌بک» یعنی هر برنامه‌ای روی همین کامپیوتر —
از جمله **هر صفحه‌ی وبی که کاربر باز کرده**. بدون فهرست مبدأ، یک سایت
تصادفی می‌توانست IMEI و سریال گوشیِ وصل‌شده را بخواند.

پس: مبدأ مرورگر باید در فهرست باشد، وگرنه ۴۰۳ — و **پیش از** آنکه
سراغ گوشی برویم رد می‌شود، تا حتی پیغام Trust هم روی گوشی نیاید.
درخواست بدون `Origin` (مثل curl از خود همین کامپیوتر) آزاد است؛
مرورگر برای درخواست بین‌مبدأ همیشه `Origin` می‌فرستد.
"""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import __version__
from .console import say
from .device import _fake_device, list_devices, now_iso, read_device
from .errors import APPLE_NOT_LISTENING, NO_DEVICE, NO_USBMUXD, BridgeError, translate
from .usbmux_find import diagnose

#: شماره‌ی قرارداد. اگر روزی شکل پاسخ عوض شد، این عدد هم عوض می‌شود و
#: رابط وب می‌فهمد که با پلِ قدیمی طرف است و می‌گوید به‌روزش کنید.
PROTOCOL = 2

#: پورت پیش‌فرض. عمداً با پل قدیمی (۱۷۳۲۵) فرق دارد تا اگر نسخه‌ی قبلی
#: هنوز روی کامپیوتری در حال اجرا بود، جواب اشتباه ندهد.
DEFAULT_PORT = 17377

#: مبدأهایی که اجازه‌ی خواندن دارند.
#: پنلِ این پروژه (Novo) روی `novo.stland.ir` است. نشانیِ قبلی (`hesabdari.stland.ir`) مهر ۱۴۰۵ کنار رفت؛
#: فایلِ اجراییِ پیش از آن با `--allow https://novo.stland.ir` همین کار را می‌کند.
#:
#: یک بار اینجا `panel.stland.ir` نوشته شده بود — که دامنه‌ی پروژه‌ی
#: **دیگری** روی همان سرور است. نتیجه‌اش این شد که پل بالا می‌آمد، پیام
#: «گوش می‌دهم» می‌داد، و بعد به هر درخواستِ پنل ۴۰۳ می‌گفت؛ پنل هم چون
#: جوابِ سالم نمی‌گرفت می‌گفت «پل اجرا نیست». یعنی خرابی جایی بود که هیچ
#: پیامی به آن اشاره نمی‌کرد.
#:
#: نامِ آن پروژه‌ی دیگر عمداً برنگشت: اگر بماند، صفحه‌های آن هم می‌توانند
#: گوشیِ وصل به این کامپیوتر را بخوانند.
DEFAULT_ORIGINS = (
    "https://novo.stland.ir",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3211",
    "http://127.0.0.1:3211",
)

#: خواندن از گوشی هم‌زمان انجام نمی‌شود: usbmuxd یک اتصال را بهتر
#: می‌پسندد و دو خواندنِ هم‌زمان به هم می‌ریزندش.
_read_lock = threading.Lock()


def _run(coro: Any) -> Any:
    """اجرای یک کوروتین در نخِ همین درخواست.

    هر نخِ سرور حلقه‌ی رویداد خودش را می‌سازد و می‌بندد؛ pymobiledevice3
    کاملاً ناهم‌زمان است ولی سرور HTTP استاندارد نخ‌محور.
    """
    return asyncio.run(coro)


class Handler(BaseHTTPRequestHandler):
    server_version = f"iPhoneBridge/{__version__}"
    #: از `Handler.allowed_origins` خوانده می‌شود؛ در `serve()` پر می‌شود
    allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS
    quiet: bool = False

    # ── کمکی‌ها ──────────────────────────────────────────────────

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True  # درخواست مستقیم از همین کامپیوتر
        return origin in self.allowed_origins

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and origin in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")

    def _json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: Any) -> None:
        if not self.quiet:
            super().log_message(fmt, *args)

    # ── مسیرها ───────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:  # noqa: N802 - نام را خود کتابخانه می‌خواهد
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"

        if not self._origin_allowed():
            self._json(403, {"ok": False, "code": "origin", "error": "این صفحه اجازه‌ی خواندن گوشی را ندارد."})
            return

        if path == "/health":
            self._json(200, {
                "ok": True,
                "bridge": "novo-iphone",
                "protocol": PROTOCOL,
                "version": __version__,
            })
            return

        if path == "/device":
            self._json(*self._device())
            return

        self._json(404, {"ok": False, "code": "not_found", "error": "چنین آدرسی نیست."})

    def _device(self) -> tuple[int, dict[str, Any]]:
        # اگر خواندنِ دیگری در جریان است، همان لحظه بگو — بهتر از صفِ
        # انتظاری که کاربر فکر کند هنگ کرده
        if not _read_lock.acquire(blocking=False):
            return 429, {
                "ok": False,
                "code": "busy",
                "error": "یک خواندن دیگر در جریان است. چند لحظه صبر کنید.",
                "retryable": True,
            }
        try:
            # با گوشیِ ساختگی (فقط در آزمون) سراغ usbmuxd نمی‌رویم
            if not _fake_device():
                # سرویسِ اپل کجا گوش می‌دهد؟ نسخه‌ی فروشگاهیِ «Apple Devices» همیشه ۲۷۰۱۵ نیست
                found = diagnose()
                if found.address is None:
                    err = APPLE_NOT_LISTENING if found.apple_processes else NO_USBMUXD
                    return 200, replace(err, detail=found.detail()).to_dict()
                serials = _run(list_devices())
                if not serials:
                    return 200, NO_DEVICE.to_dict()
            device = _run(read_device())
            return 200, {"ok": True, "readAt": now_iso(), "device": device}
        except BridgeError as err:
            return 200, err.to_dict()
        except Exception as exc:  # pragma: no cover - شبکه‌ی خراب
            return 200, translate(exc).to_dict()
        finally:
            _read_lock.release()


def make_server(port: int, origins: tuple[str, ...], *, quiet: bool = False) -> ThreadingHTTPServer:
    """سرور را می‌سازد ولی اجرا نمی‌کند — تا آزمون بتواند پورت واقعی را بخواند."""

    class Bound(Handler):
        allowed_origins = origins

    Bound.quiet = quiet
    # فقط لوپ‌بک: هیچ‌کس از شبکه‌ی فروشگاه به گوشی نمی‌رسد
    return ThreadingHTTPServer(("127.0.0.1", port), Bound)


def serve(port: int = DEFAULT_PORT, origins: tuple[str, ...] = DEFAULT_ORIGINS) -> None:
    httpd = make_server(port, origins)
    real_port = httpd.server_address[1]
    say(f"iPhone Bridge {__version__} is listening on http://127.0.0.1:{real_port}")
    say("Allowed pages:")
    for origin in origins:
        say(f"  - {origin}")
    found = diagnose()
    if found.address:
        say(f"Apple service: OK on {found.address}")
    else:
        say(f"Apple service: NOT FOUND ({found.detail()})")
        say("  Open Apple Devices (or iTunes) once, or restart this computer.")
    say("Keep this window open. Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        say("")
        say("Stopped.")
    finally:
        httpd.server_close()
