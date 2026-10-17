"""شناسه‌ی داخلی اپل → نام بازاری، و بایت → ظرفیت بازاری.

منبع نام‌ها **جدول خودِ pymobiledevice3** است (`IRECV_DEVICES`)، نه یک
فهرست دستیِ ما. آن جدول با هر نسخه‌ی کتابخانه به‌روز می‌شود و همین حالا
تا iPhone 17e را دارد؛ فهرست دستی از روز اول عقب می‌افتد.

اگر شناسه در جدول نبود، **حدس نمی‌زنیم**: `None` برمی‌گردد و رابط کاربری
خودش می‌گوید مدل را دستی انتخاب کنید. یک نام اشتباه بدتر از نامِ خالی
است، چون کسی به آن شک نمی‌کند.
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    from pymobiledevice3.irecv_devices import IRECV_DEVICES

    out: dict[str, str] = {}
    for device in IRECV_DEVICES:
        # چند سطر برای یک شناسه هست (بردهای مختلف با یک نام)؛ اولی کافی است
        out.setdefault(device.product_type, device.display_name)
    return out


def marketing_name(product_type: str | None) -> str | None:
    """«iPhone18,2» → «iPhone 17 Pro Max»، یا None اگر ناشناخته باشد."""
    if not product_type:
        return None
    return _table().get(product_type.strip())


#: ظرفیت‌هایی که اپل واقعاً فروخته. چیزی بیرون این فهرست یعنی
#: اندازه‌گیری ما اشتباه بوده، نه اینکه گوشی ظرفیت عجیبی دارد.
CAPACITIES_GB: tuple[int, ...] = (16, 32, 64, 128, 256, 512, 1024, 2048)


def marketing_capacity_gb(total_bytes: object) -> int | None:
    """ظرفیت خام دیسک → ظرفیت بازاری.

    گوشیِ «۲۵۶ گیگ» حدود ۲۵۱ میلیارد بایت گزارش می‌کند: بخشی از فلش برای
    سیستم فایل و بلوک‌های یدکی کنار گذاشته می‌شود. پس نزدیک‌ترین ظرفیتِ
    رسمیِ **بزرگ‌تر یا برابر** را برمی‌گردانیم، و فقط اگر فاصله معقول
    باشد؛ وگرنه None، چون عدد اشتباه بدتر از عدد نداشتن است.
    """
    try:
        raw = float(total_bytes)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if raw <= 0:
        return None

    gb = raw / 1_000_000_000
    for size in CAPACITIES_GB:
        # کف ۸۰٪: ۲۵۶ گیگ واقعی حدود ۹۸٪ است، ولی گوشی‌های قدیمی‌تر
        # سخاوت کمتری داشتند. سقف ۱۰۵٪ جلوی «۱۲۸ را ۲۵۶ خواندن» را می‌گیرد.
        if size * 0.80 <= gb <= size * 1.05:
            return size
    return None
