"""قراردادِ بین پل و برنامه‌ی وب.

`contract/iphone-sample.json` را همین کد می‌سازد و **سمت وب هم از همان
می‌خواند**. پس اگر روزی شکل خروجی پل عوض شود، این آزمون قرمز می‌شود و
یادآوری می‌کند که فایل قرارداد را دوباره بسازید — و آن‌وقت آزمون‌های
TypeScript هم روی شکل تازه اجرا می‌شوند.

بدون این، دو طرف بی‌سروصدا از هم دور می‌افتند و اولین جایی که معلوم
می‌شد، کامپیوتر فروشگاه بود.

برای ساختن دوباره:

    python -m tests.test_contract
"""

from __future__ import annotations

import json
from pathlib import Path

from iphone_bridge.device import build_payload

from .test_device import BATTERY, DISK, VALUES

CONTRACT = Path(__file__).resolve().parent.parent / "contract" / "iphone-sample.json"


def sample() -> dict:
    return {
        "ok": True,
        "readAt": "2026-09-08T12:00:00Z",
        "device": build_payload(VALUES, DISK, BATTERY),
    }


def test_the_checked_in_contract_matches_what_the_bridge_produces():
    stored = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert stored == sample(), (
        "شکل خروجی پل عوض شده. فایل قرارداد را دوباره بسازید:\n"
        "    cd bridge && python -m tests.test_contract"
    )


def test_the_contract_keeps_the_promises_the_web_app_relies_on():
    device = json.loads(CONTRACT.read_text(encoding="utf-8"))["device"]
    # رنگ هرگز حدس زده نمی‌شود — این را هر دو طرف روی آن حساب کرده‌اند
    assert device["color"] is None
    # فیلدهایی که فرم ثبت کالا مستقیم پر می‌کند
    for key in ("marketingName", "storageGb", "regionInfo", "imei", "imei2", "serialNumber"):
        assert key in device, f"«{key}» از قرارداد افتاده — فرم کالا رویش حساب کرده"
    assert device["battery"]["healthPercent"] is not None


if __name__ == "__main__":  # pragma: no cover - ابزار، نه آزمون
    CONTRACT.parent.mkdir(exist_ok=True)
    CONTRACT.write_text(json.dumps(sample(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"نوشته شد: {CONTRACT}")
