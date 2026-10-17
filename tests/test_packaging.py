"""نگهبانِ فایل ساخت.

اولین `iPhoneBridge.exe` ساخته شد، `--version` هم جواب داد، ولی موقع
اجرا نتوانست pymobiledevice3 را ایمپورت کند: روی ویندوز خودِ کتابخانه
هنگام ایمپورت `lockdown` سراغ `osu.win_util` می‌رود و آن به pywin32 و
`ifaddr` تکیه دارد — چیزهایی که در کدِ ما هیچ‌جا ایمپورت نمی‌شوند، پس
PyInstaller با ردیابی معمولی پیدایشان نمی‌کند.

این آزمون روی لینوکس هم اجرا می‌شود (جایی که اصلاً ویندوزی در کار نیست)
تا اگر کسی آن بخش از spec را «تمیزکاری» کرد، همین‌جا قرمز شود نه روی
کامپیوتر فروشگاه.
"""

from pathlib import Path

import pytest

SPEC = Path(__file__).resolve().parent.parent / "iPhoneBridge.spec"


def spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def test_spec_exists() -> None:
    assert SPEC.is_file(), f"فایل ساخت نیست: {SPEC}"


@pytest.mark.parametrize(
    "module",
    [
        # زنجیره‌ای که روی ویندوز هنگام ایمپورت lockdown باز می‌شود
        "pymobiledevice3.osu.win_util",
        "win32security",
        "ifaddr",
        # قلابِ pywintypes است که pywintypes3xx.dll را کنار EXE می‌گذارد،
        # و فقط وقتی اجرا می‌شود که pywin32 در گراف ایمپورت دیده شود
        "pywintypes",
    ],
)
def test_windows_chain_is_declared(module: str) -> None:
    assert f'"{module}"' in spec_text(), (
        f"«{module}» در iPhoneBridge.spec نیست. بدون آن، فایل اجرایی ساخته "
        "می‌شود ولی روی ویندوز موقع ایمپورت lockdown می‌شکند."
    )


def test_chardet_stays_out() -> None:
    """chardet با mypyc کامپایل شده و داخل فایل اجرایی نمی‌شکفد.

    روی لینوکس اتفاقی نسخه‌ی `.py` برداشته می‌شود و همه‌چیز سبز است؛ روی
    ویندوز `.pyd` برداشته می‌شود و ایمپورتِ `lockdown` با SystemError
    می‌شکند — خطایی که `except ImportError` خودِ requests هم نمی‌گیردش.
    پس اینجا آزمونِ لینوکسی نمی‌تواند خرابی را ببیند و همین سطر تنها
    نگهبانش است.
    """
    text = spec_text()
    assert '"chardet"' in text, "chardet دوباره وارد فایل اجرایی شده"
    assert '"charset_normalizer"' in text, (
        "جانشین chardet نیست؛ requests با importlib صدایش می‌زند و "
        "ردیابی معمولی PyInstaller پیدایش نمی‌کند"
    )


def test_the_reason_is_written_down() -> None:
    """چراییِ آن فهرست باید کنارش بماند، وگرنه دفعه‌ی بعد پاک می‌شود."""
    text = spec_text()
    assert "win32" in text and "lockdown" in text, (
        "توضیحِ اینکه چرا این ماژول‌ها دستی اضافه شده‌اند از spec حذف شده"
    )


def test_selftest_checks_the_platform_helper() -> None:
    """`selftest` باید همان چیزی را بسنجد که شکسته بود.

    وگرنه ساختِ بعدی دوباره سبز می‌شود و خرابی تازه روی کامپیوتر فروشگاه
    پیدا می‌شود.
    """
    main = (Path(__file__).resolve().parent.parent / "iphone_bridge" / "__main__.py").read_text(
        encoding="utf-8"
    )
    assert "pymobiledevice3.osu.os_utils" in main, "selftest دیگر osu را نمی‌سنجد"
    assert "get_os_utils()" in main, "selftest دیگر ساختِ OsUtils را نمی‌سنجد"
