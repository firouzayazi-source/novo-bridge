"""خواندن مشخصات آیفونِ وصل‌شده به کابل.

دو منبع، هر دو روی خودِ دستگاه:

* **lockdown** — همان چیزی که iTunes می‌خواند: نام، مدل، سریال، IMEI،
  نسخه‌ی iOS، ظرفیت دیسک. بدون نیاز به Developer Mode.
* **IORegistry** از سرویس diagnostics — فقط برای باتری
  (`IOPMPowerSource`): ظرفیت طراحی، ظرفیت فعلی و تعداد شارژ.

عمداً از MobileGestalt استفاده نمی‌شود: اپل از iOS ۱۷.۴ منسوخش کرده و
خودِ pymobiledevice3 روی آن استثنا پرتاب می‌کند.

─── قاعده‌ای که این فایل بر آن بنا شده ───

**هیچ‌چیز حدس زده نمی‌شود.** هر فیلدی که دستگاه نداد یا نشد مطمئن
خواندش، `None` برمی‌گردد و رابط کاربری خالی نشانش می‌دهد. یک مقدار
اشتباه بدتر از خالی است، چون کسی به آن شک نمی‌کند و ماه‌ها بعد در
دفاتر پیدا می‌شود.

بارزترینش **رنگ** است: اپل کدی مثل `1` یا `#3b3b3c` می‌دهد که نگاشت
پایداری به «Deep Blue» ندارد و از مدلی به مدل دیگر عوض می‌شود. پس
`color` همیشه `None` است و کد خام جدا برمی‌گردد تا اگر روزی منبع
قابل‌اعتمادی پیدا شد، بشود ازش استفاده کرد.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .errors import BridgeError, translate
from .marketing import marketing_capacity_gb, marketing_name

#: کلیدهای lockdown که لازم داریم. بقیه‌ی خروجی دستگاه — مثل کلید عمومی
#: و شناسه‌های داخلی — اصلاً از پل بیرون نمی‌رود.
LOCKDOWN_KEYS = (
    "DeviceName",
    "ProductType",
    "ProductVersion",
    "BuildVersion",
    "SerialNumber",
    "InternationalMobileEquipmentIdentity",
    "InternationalMobileEquipmentIdentity2",
    "UniqueDeviceID",
    "ModelNumber",
    "RegionInfo",
    "DeviceColor",
    "DeviceEnclosureColor",
    "HardwareModel",
    "CPUArchitecture",
)

COLOR_NOTE = "رنگ از روی کابل قابل اعتماد نیست — خودتان انتخابش کنید."
BATTERY_NOTE = "سلامت باتری از این دستگاه خوانده نشد."
MODEL_NOTE = "مدل این دستگاه در جدول شناخته‌شده نیست — دستی انتخابش کنید."


def _text(value: Any) -> str | None:
    """رشته‌ی تمیز، یا None. رشته‌ی خالی هم یعنی «نداریم»."""
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", "ignore")
        except Exception:  # pragma: no cover - بایتِ خراب
            return None
    text = str(value).strip()
    return text or None


def _digits(value: Any) -> str | None:
    """IMEI را دستگاه گاهی با فاصله می‌دهد؛ فقط رقم‌ها می‌مانند."""
    text = _text(value)
    if text is None:
        return None
    only = "".join(ch for ch in text if ch.isdigit())
    return only or None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def part_number(model_number: str | None, region_info: str | None) -> str | None:
    """«MFYM4» + «ZA/A» → «MFYM4ZA/A».

    بعضی دستگاه‌ها `ModelNumber` را از قبل با منطقه می‌دهند («MFYM4ZA»)؛
    آن‌وقت دوباره نمی‌چسبانیم. اگر یکی از دو تکه نبود، چیزی نمی‌سازیم.
    """
    model = _text(model_number)
    region = _text(region_info)
    if not model:
        return None
    if not region:
        return model
    letters = region.split("/")[0]
    if letters and model.upper().endswith(letters.upper()):
        return f"{model}/{region.split('/')[-1]}" if "/" in region else model
    return f"{model}{region}"


def battery_from_ioregistry(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """`IOPMPowerSource` → سلامت باتری.

    «سلامت باتری» همان چیزی است که خود آیفون در تنظیمات نشان می‌دهد:
    نسبت ظرفیت واقعی به ظرفیت طراحی. اپل در iOS جدید
    `NominalChargeCapacity` را مبنا می‌گیرد و در نسخه‌های قدیمی‌تر
    `AppleRawMaxCapacity`. هر کدام بود استفاده می‌شود و **اسمش هم
    برمی‌گردد** تا عدد قابل ردیابی باشد.

    اگر ظرفیت طراحی نبود، درصدی حساب نمی‌کنیم — عددی که مخرجش را
    نمی‌دانیم بی‌معنی است.
    """
    if not entry:
        return None

    design = _number(entry.get("DesignCapacity"))
    nominal = _number(entry.get("NominalChargeCapacity"))
    raw_max = _number(entry.get("AppleRawMaxCapacity"))
    cycles = _number(entry.get("CycleCount"))
    current = _number(entry.get("CurrentCapacity"))

    out: dict[str, Any] = {
        "healthPercent": None,
        "basis": None,
        "designCapacity": int(design) if design else None,
        "maxCapacity": None,
        "cycleCount": int(cycles) if cycles is not None else None,
        "currentPercent": int(current) if current is not None and 0 <= current <= 100 else None,
    }

    measured, basis = (nominal, "NominalChargeCapacity") if nominal else (raw_max, "AppleRawMaxCapacity")
    if measured:
        out["maxCapacity"] = int(measured)
        out["basis"] = basis
    if measured and design and design > 0:
        percent = round(measured / design * 100)
        # باتری سالمِ نو گاهی کمی بالای ۱۰۰ درمی‌آید؛ بالاتر از آن یعنی
        # عددها به هم نمی‌خورند و بهتر است چیزی نگوییم
        if 0 < percent <= 110:
            out["healthPercent"] = min(percent, 100)

    if out["healthPercent"] is None and out["cycleCount"] is None and out["currentPercent"] is None:
        return None
    return out


def build_payload(
    values: dict[str, Any],
    disk: dict[str, Any] | None,
    battery_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """مقدارهای خام دستگاه → همان چیزی که به مرورگر می‌رود.

    جدا از خواندن نگه داشته شده تا بشود بدون آیفون سنجیدش: ورودی‌اش
    همان دیکشنری‌هایی است که lockdown و IORegistry می‌دهند.
    """
    product_type = _text(values.get("ProductType"))
    model = marketing_name(product_type)
    total_bytes = (disk or {}).get("TotalDiskCapacity")
    storage_gb = marketing_capacity_gb(total_bytes)
    battery = battery_from_ioregistry(battery_entry)

    notes: list[str] = [COLOR_NOTE]
    if product_type and not model:
        notes.append(MODEL_NOTE)
    if battery is None:
        notes.append(BATTERY_NOTE)

    return {
        "deviceName": _text(values.get("DeviceName")),
        "marketingName": model,
        "productType": product_type,
        "modelNumber": _text(values.get("ModelNumber")),
        "regionInfo": _text(values.get("RegionInfo")),
        "partNumber": part_number(values.get("ModelNumber"), values.get("RegionInfo")),
        "iosVersion": _text(values.get("ProductVersion")),
        "buildVersion": _text(values.get("BuildVersion")),
        "serialNumber": _text(values.get("SerialNumber")),
        "imei": _digits(values.get("InternationalMobileEquipmentIdentity")),
        "imei2": _digits(values.get("InternationalMobileEquipmentIdentity2")),
        "udid": _text(values.get("UniqueDeviceID")),
        "storageGb": storage_gb,
        "storageBytes": int(total_bytes) if isinstance(total_bytes, (int, float)) else None,
        "battery": battery,
        # هرگز حدس زده نمی‌شود؛ کد خام برای روزی که منبع مطمئنی پیدا شود
        "color": None,
        "colorCodes": {
            "deviceColor": _text(values.get("DeviceColor")),
            "enclosureColor": _text(values.get("DeviceEnclosureColor")),
        },
        "notes": notes,
    }


async def _read_battery(lockdown: Any) -> dict[str, Any] | None:
    """باتری اختیاری است: اگر نشد، بقیه‌ی مشخصات نباید از دست برود."""
    try:
        from pymobiledevice3.services.diagnostics import DiagnosticsService

        service = DiagnosticsService(lockdown)
        entry = await asyncio.wait_for(service.get_battery(), timeout=15)
        return entry if isinstance(entry, dict) else None
    except Exception:
        return None


async def _read_disk(lockdown: Any) -> dict[str, Any] | None:
    try:
        disk = await lockdown.get_value(domain="com.apple.disk_usage")
        return disk if isinstance(disk, dict) else None
    except Exception:
        return None


def _fake_device() -> dict[str, Any] | None:
    """گوشیِ ساختگی برای آزمون — فقط وقتی `BRIDGE_FAKE_DEVICE` تعریف شده.

    آزمون سرتاسری باید ثابت کند زنجیره‌ی «پل → مرورگر → فرم» کار می‌کند،
    ولی هیچ آیفونی به ماشین CI وصل نیست. این دریچه اجازه می‌دهد **خودِ
    پل واقعی** اجرا شود و فقط جای گفت‌وگو با USB، یک فایل خوانده شود.

    عمداً متغیر محیطی است نه پرچم خط فرمان: کسی به‌طور اتفاقی روی
    کامپیوتر فروشگاه فعالش نمی‌کند.
    """
    import os

    path = os.environ.get("BRIDGE_FAKE_DEVICE")
    if not path:
        return None
    import json

    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("device", data)


async def read_device(*, pair_timeout: float = 25.0, udid: str | None = None) -> dict[str, Any]:
    """آیفونِ وصل‌شده را می‌خواند. در صورت مشکل `BridgeError` پرتاب می‌کند."""
    fake = _fake_device()
    if fake is not None:
        return fake

    from pymobiledevice3.lockdown import create_using_usbmux

    lockdown = None
    try:
        # autopair یعنی اگر جفت نشده، پیغام Trust روی گوشی بیاید — همان
        # کاری که کاربر انتظارش را دارد. مهلت می‌گذاریم تا اگر کسی گوشی
        # را دست نگرفت، پل تا ابد منتظر نماند.
        lockdown = await create_using_usbmux(
            serial=udid,
            autopair=True,
            pair_timeout=pair_timeout,
            connection_type="USB",
        )
        values = dict(lockdown.all_values or {})
        # فقط کلیدهای لازم؛ بقیه‌ی خروجی دستگاه از پل بیرون نمی‌رود
        wanted = {key: values.get(key) for key in LOCKDOWN_KEYS}
        disk = await _read_disk(lockdown)
        battery = await _read_battery(lockdown)
        return build_payload(wanted, disk, battery)
    except BridgeError:
        raise
    except Exception as exc:
        raise translate(exc) from exc
    finally:
        if lockdown is not None:
            try:
                await lockdown.close()
            except Exception:
                pass


async def list_devices() -> list[str]:
    """شناسه‌ی دستگاه‌های وصل‌شده — برای پیام «گوشی وصل نیست»."""
    try:
        from pymobiledevice3.usbmux import list_devices as _list

        devices = await _list()
        return [d.serial for d in devices if getattr(d, "connection_type", "USB") == "USB"]
    except Exception as exc:
        raise translate(exc) from exc


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
