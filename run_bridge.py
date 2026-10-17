"""نقطه‌ی ورود فایل اجرایی.

PyInstaller به یک اسکریپت ساده نیاز دارد، نه `-m package`؛ این فایل
فقط همان `main` را صدا می‌زند تا رفتار EXE و اجرای معمولی یکی باشد.
"""

import multiprocessing
import sys

from iphone_bridge.__main__ import main

if __name__ == "__main__":
    # روی ویندوز، فایل اجرایی‌ای که فرزند بسازد بدون این خودش را دوباره
    # اجرا می‌کند. ما فرزند نمی‌سازیم، ولی کتابخانه‌های زیرین ممکن است.
    multiprocessing.freeze_support()
    sys.exit(main())
