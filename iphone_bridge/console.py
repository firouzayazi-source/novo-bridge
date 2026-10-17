"""چاپ روی کنسول، بدون اینکه هیچ‌وقت بترکد.

کنسول ویندوز به‌طور پیش‌فرض cp1252 است. هر حرف فارسی که به آن برسد
`UnicodeEncodeError` می‌دهد و **کل برنامه می‌ایستد** — نه اینکه فقط بد
نشان دهد. یک بار همین، `selftest` را وسط کار انداخت، آن هم بعد از اینکه
همه‌ی سنجش‌ها سبز شده بودند.

پس یک راهِ خروج بیشتر نداریم و همه از آن رد می‌شوند. متن به ASCII تبدیل
می‌شود؛ هرچه نشد، به شکل `\\uXXXX` درمی‌آید. زشت است ولی خوانا و
بی‌خطر — و به هر حال conhost فارسی را وارونه نشان می‌دهد، پس پیام فارسی
جایش داخل JSON است که مرورگر نشانش می‌دهد، نه اینجا.
"""

from __future__ import annotations

import sys


def ascii_only(text: str) -> str:
    """هر چیزی که ASCII نیست، به `\\uXXXX` تبدیل می‌شود."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def say(text: str = "") -> None:
    """تنها راهِ چاپ در این برنامه."""
    sys.stdout.write(ascii_only(text) + "\n")
    sys.stdout.flush()
