"""سرور محلی: چه چیزی می‌دهد، و مهم‌تر — به چه کسی نمی‌دهد.

پل روی لوپ‌بک است، ولی لوپ‌بک یعنی هر برنامه‌ای روی همین کامپیوتر،
از جمله هر صفحه‌ی وبی که کاربر باز کرده. اگر فهرست مبدأ بشکند، یک سایت
تصادفی می‌تواند IMEI و سریال گوشیِ وصل‌شده را بخواند.
"""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from iphone_bridge.server import PROTOCOL, make_server

# آدرس پنلِ خودمان. عمداً دامنه‌ی پروژه‌های دیگرِ روی همان سرور اینجا
# نوشته نمی‌شود — حتی به‌عنوان نمونه‌ی آزمون — تا کسی از روی آن کپی نکند.
ALLOWED = "https://novo.stland.ir"


@pytest.fixture
def bridge():
    httpd = make_server(0, (ALLOWED,), quiet=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def get(url: str, origin: str | None = None):
    request = urllib.request.Request(url)
    if origin:
        request.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode()), dict(response.headers)
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode()), dict(err.headers)


def test_health_names_itself_and_its_protocol(bridge):
    base, _ = bridge
    status, body, _ = get(f"{base}/health")
    assert status == 200
    assert body["ok"] is True
    assert body["bridge"] == "novo-iphone"
    assert body["protocol"] == PROTOCOL


def test_the_panel_may_read(bridge):
    base, _ = bridge
    status, _, headers = get(f"{base}/health", origin=ALLOWED)
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == ALLOWED
    assert headers.get("Vary") == "Origin"


def test_any_other_page_is_refused(bridge):
    base, _ = bridge
    status, body, headers = get(f"{base}/device", origin="https://attacker.example")
    assert status == 403
    assert body["code"] == "origin"
    assert "Access-Control-Allow-Origin" not in headers, "مبدأ رد شده نباید مجوز بگیرد"


def test_a_refused_page_never_reaches_the_phone(bridge, monkeypatch):
    """رد کردن باید **پیش از** سراغ گوشی رفتن باشد.

    وگرنه یک سایت مهاجم می‌تواند پیغام Trust را روی گوشی بیاورد، حتی
    اگر جواب را نخواند.
    """
    import iphone_bridge.server as server

    touched: list[str] = []

    async def boom():
        touched.append("listed")
        return ["x"]

    monkeypatch.setattr(server, "list_devices", boom)
    base, _ = bridge
    get(f"{base}/device", origin="https://attacker.example")
    assert touched == [], "به گوشی دست زده شد"


def test_no_phone_gives_a_clear_message_not_a_crash(bridge):
    # روی این ماشین نه usbmuxd هست نه آیفون — همان دو حالتی که کاربر هم می‌بیند
    base, _ = bridge
    status, body, _ = get(f"{base}/device")
    assert status == 200, "نبود گوشی خطای سرور نیست"
    assert body["ok"] is False
    assert body["error"], "باید بگوید چه شده"
    assert body["code"] in {"no_device", "no_usbmuxd", "unknown"}
    # پیام باید فارسی و برای کاربر باشد، نه نام یک استثنا
    assert not body["error"].startswith(("Traceback", "Error", "Exception"))


def test_unknown_paths_are_not_found(bridge):
    base, _ = bridge
    status, body, _ = get(f"{base}/../etc/passwd")
    assert status == 404
    assert body["ok"] is False


def test_preflight_is_answered(bridge):
    base, _ = bridge
    request = urllib.request.Request(f"{base}/device", method="OPTIONS")
    request.add_header("Origin", ALLOWED)
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 204
        assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED


def test_it_listens_only_on_loopback(bridge):
    """اگر روی ۰.۰.۰.۰ گوش می‌داد، هرکسی روی شبکه‌ی فروشگاه می‌رسید."""
    _, port = bridge
    addresses = [
        info[4][0]
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        if not info[4][0].startswith("127.")
    ]
    if not addresses:
        pytest.skip("این ماشین آدرس بیرونی ندارد")
    with socket.socket() as sock:
        sock.settimeout(2)
        with pytest.raises(OSError):
            sock.connect((addresses[0], port))


def test_the_panel_domain_is_the_right_one() -> None:
    """آدرس پنلِ **این** پروژه، نه پروژه‌ی دیگرِ روی همان سرور.

    یک بار اینجا `panel.stland.ir` نوشته شده بود که دامنه‌ی پروژه‌ی دیگری
    است. پل بالا می‌آمد، «گوش می‌دهم» می‌گفت، و بعد به هر درخواستِ پنل ۴۰۳
    می‌داد؛ صفحه هم فقط می‌گفت «پل اجرا نیست» — یعنی تنها چیزی که کاربر
    می‌دید دقیقاً چیزی بود که مشکل نبود.
    """
    from iphone_bridge.server import DEFAULT_ORIGINS

    # نامِ سیستم Novo؛ نشانیِ قبلی عمداً کنار رفت (مهر ۱۴۰۵)
    assert "https://novo.stland.ir" in DEFAULT_ORIGINS
    assert not any("hesabdari" in o for o in DEFAULT_ORIGINS)
    # دامنه‌ی آن پروژه‌ی دیگر نباید برگردد: صفحه‌هایش نباید بتوانند گوشیِ
    # وصل به این کامپیوتر را بخوانند
    assert not any("panel.stland.ir" in o for o in DEFAULT_ORIGINS)
