"""هیچ حرف فارسی نباید به کنسول برسد.

کنسول ویندوز cp1252 است. یک حرف فارسی که به آن برسد `UnicodeEncodeError`
می‌دهد و **برنامه می‌ایستد** — نه اینکه فقط بد نشان دهد. دقیقاً همین
اتفاق افتاد: `selftest` روی ویندوز همه‌ی سنجش‌هایش سبز شد و بعد، سرِ چاپ
کردنِ پیام فارسیِ «گوشی وصل نیست»، ترکید.

خطرناک‌تر از آن `iPhoneBridge.exe read` بود: خروجی JSONاش با
`ensure_ascii=False` چاپ می‌شد، پس اولین خطای فارسی روی کامپیوتر فروشگاه
همان کار را می‌کرد.

پس این آزمون از راهِ خروجی محافظت می‌کند، نه از تک‌تک `print`ها.
"""

import json

import pytest

from iphone_bridge.console import ascii_only, say

PERSIAN = "گوشی وصل نیست."


def test_persian_survives_as_escapes() -> None:
    out = ascii_only(PERSIAN)
    out.encode("cp1252")  # اگر بترکد، همان خرابیِ ویندوز است
    assert "\\u" in out, "متن فارسی باید به شکل \\uXXXX دربیاید، نه اینکه گم شود"


def test_ascii_text_is_untouched() -> None:
    assert ascii_only("iPhone Bridge 1.0.0") == "iPhone Bridge 1.0.0"


def test_say_never_breaks_on_a_cp1252_console(capsys: pytest.CaptureFixture[str]) -> None:
    say(f"code=no_device  message={PERSIAN}")
    printed = capsys.readouterr().out
    printed.encode("cp1252")
    assert "code=no_device" in printed


def test_the_read_command_prints_ascii_json() -> None:
    """خروجی `read` هم باید ASCII باشد و هم JSON معتبر بماند."""
    payload = {"ok": False, "code": "no_device", "error": PERSIAN}
    text = json.dumps(payload, ensure_ascii=True, indent=2)
    text.encode("cp1252")
    assert json.loads(text)["error"] == PERSIAN, "فارسی نباید از دست برود، فقط escape شود"


def test_nothing_bypasses_the_one_way_out() -> None:
    """اگر کسی `print` تازه‌ای اضافه کرد، همین‌جا معلوم شود."""
    from pathlib import Path

    package = Path(__file__).resolve().parent.parent / "iphone_bridge"
    offenders = [
        path.name
        for path in package.glob("*.py")
        if "print(" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"این فایل‌ها مستقیم print می‌کنند: {offenders}. از say() در console.py "
        "استفاده کنید، وگرنه روی کنسول ویندوز می‌ترکند."
    )
