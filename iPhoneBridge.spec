# -*- mode: python ; coding: utf-8 -*-
"""ساخت iPhoneBridge.exe — یک فایل، بدون نصب پایتون روی کامپیوتر مقصد.

`collect_all` لازم است چون pymobiledevice3 هم زیرماژول‌های زیادی دارد که
فقط در زمان اجرا ایمپورت می‌شوند و هم فایل‌های داده (`resources/`).
PyInstaller بدون این، ایمیج را می‌سازد ولی موقع اجرا ماژول گم می‌شود —
و آن‌وقت روی کامپیوتر فروشگاه معلوم می‌شود، نه اینجا. برای همین
`selftest` در CI بلافاصله بعد از ساخت اجرا می‌شود.
"""

import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = collect_all("pymobiledevice3")

# رمزنگاری: بک‌اند در زمان اجرا انتخاب می‌شود، پس PyInstaller خودش
# پیدایش نمی‌کند
hiddenimports += collect_submodules("cryptography")
hiddenimports += [
    "asyncio",
    "asyncio.selector_events",
    "asyncio.windows_events",
    # جانشین chardet که پایین‌تر کنار گذاشته شده. requests خودش با
    # importlib صدایش می‌زند، پس ردیابی معمولی پیدایش نمی‌کند.
    "charset_normalizer",
]

# ─── ویندوز ───
#
# `lockdown.py` در همان خطِ ایمپورت `get_os_utils()` را صدا می‌زند، و آن
# روی ویندوز `pymobiledevice3.osu.win_util` را می‌آورد که به pywin32
# (`win32security`) و `ifaddr` تکیه دارد. هیچ‌کدام از این‌ها در کدِ ما
# ایمپورت نمی‌شوند، پس PyInstaller با ردیابی معمولی پیدایشان نمی‌کند و
# فایل اجرایی ساخته می‌شود ولی موقع اجرا می‌شکند.
#
# اولین ساختِ EXE دقیقاً همین‌جا شکست: خودِ فایل ساخته شد و `--version`
# هم جواب داد، ولی `selftest` نتوانست pymobiledevice3 را ایمپورت کند.
# نامِ صریحِ `win32security` لازم است چون قلاب `hook-pywintypes` تنها
# وقتی اجرا می‌شود که pywin32 در گراف ایمپورت دیده شود — و همان قلاب است
# که `pywintypes3xx.dll` را کنار فایل اجرایی می‌گذارد.
if sys.platform == "win32":
    hiddenimports += [
        "pymobiledevice3.osu.win_util",
        "ifaddr",
        "pywintypes",
        "win32security",
        "win32api",
        "win32con",
        "win32file",
        "win32timezone",
    ]

a = Analysis(
    ["run_bridge.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # چیزهایی که pymobiledevice3 برای کارهای دیگر لازم دارد و ما نه؛
    # بدون این‌ها فایل اجرایی ده‌ها مگابایت بزرگ‌تر می‌شود
    excludes=[
        "IPython",
        "matplotlib",
        "pytest",
        "tkinter",
        "PIL",
        "pandas",
        "numpy",
        # chardet با mypyc کامپایل شده و ماژول‌های کامپایل‌شده‌اش
        # (`language__mypyc` و برادرانش) داخل فایل اجرایی پیدا نمی‌شوند.
        # روی لینوکس اتفاقی نسخه‌ی .py برداشته می‌شود و کار می‌کند، ولی
        # روی ویندوز .pyd برداشته می‌شود و همان‌جا می‌شکند — با
        # SystemError، که حتی `except ImportError` خودِ requests هم
        # نمی‌گیردش.
        #
        # لازمش هم نداریم: تنها راهش requests است (که خودِ
        # pymobiledevice3 برای کارهای دیگر ایمپورت می‌کند) و requests
        # اگر نبود سراغ charset_normalizer می‌رود و اگر آن هم نبود
        # utf-8 فرض می‌کند. پل اصلاً درخواست HTTP نمی‌فرستد.
        "chardet",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="iPhoneBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # پنجره‌ی مشکی لازم است: کاربر باید ببیند پل بالاست و بتواند ببندد
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
