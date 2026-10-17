"""ساختِ خروجی پل، روی همان شکلی که دستگاه واقعی می‌دهد.

نکته‌ی این آزمون‌ها «می‌خواند یا نه» نیست — آن را فقط با آیفون واقعی
می‌شود فهمید. اینجا چیزی سنجیده می‌شود که **بدون گوشی هم خراب می‌شود**:

  • فیلدی که دستگاه نداد، نباید حدس زده شود؛
  • رنگ هرگز پر نشود؛
  • فقط کلیدهای لازم بیرون بروند، نه هر چه دستگاه گفت؛
  • درصد باتری وقتی مخرجش معلوم نیست، ساخته نشود.
"""

from __future__ import annotations

import pytest

from iphone_bridge.device import (
    LOCKDOWN_KEYS,
    battery_from_ioregistry,
    build_payload,
    part_number,
)
from iphone_bridge.marketing import marketing_capacity_gb, marketing_name

# همان شکلی که lockdown برای یک iPhone 17 Pro Max می‌دهد
VALUES = {
    "DeviceName": "Ali's iPhone",
    "ProductType": "iPhone18,2",
    "ProductVersion": "26.0.1",
    "BuildVersion": "23A341",
    "SerialNumber": "MLJJYN7QMH",
    "InternationalMobileEquipmentIdentity": "35 673884 570421 7",
    "InternationalMobileEquipmentIdentity2": "356738845949911",
    "UniqueDeviceID": "00008140-000A4D2E0C61801C",
    "ModelNumber": "MFYM4",
    "RegionInfo": "ZA/A",
    "DeviceColor": "1",
    "DeviceEnclosureColor": "2",
}

DISK = {"TotalDiskCapacity": 251_000_000_000, "TotalDataAvailable": 190_000_000_000}

BATTERY = {
    "DesignCapacity": 4685,
    "NominalChargeCapacity": 4400,
    "AppleRawMaxCapacity": 4402,
    "CycleCount": 132,
    "CurrentCapacity": 78,
}


def test_reads_every_field_of_a_real_label():
    out = build_payload(VALUES, DISK, BATTERY)
    assert out["deviceName"] == "Ali's iPhone"
    assert out["marketingName"] == "iPhone 17 Pro Max"
    assert out["productType"] == "iPhone18,2"
    assert out["iosVersion"] == "26.0.1"
    assert out["serialNumber"] == "MLJJYN7QMH"
    assert out["udid"] == "00008140-000A4D2E0C61801C"
    assert out["storageGb"] == 256
    assert out["regionInfo"] == "ZA/A"
    assert out["partNumber"] == "MFYM4ZA/A"


def test_imei_loses_the_spaces_the_device_puts_in():
    out = build_payload(VALUES, DISK, BATTERY)
    assert out["imei"] == "356738845704217"
    assert out["imei2"] == "356738845949911"


def test_colour_is_never_guessed():
    out = build_payload(VALUES, DISK, BATTERY)
    assert out["color"] is None, "کد رنگ اپل نگاشت پایداری ندارد — نباید حدس زده شود"
    assert out["colorCodes"] == {"deviceColor": "1", "enclosureColor": "2"}
    assert any("رنگ" in note for note in out["notes"])


def test_missing_fields_stay_empty_instead_of_being_invented():
    out = build_payload({"ProductType": "iPhone18,2"}, None, None)
    assert out["serialNumber"] is None
    assert out["imei"] is None
    assert out["imei2"] is None
    assert out["storageGb"] is None
    assert out["battery"] is None
    # ولی چیزی که واقعاً معلوم است، هست
    assert out["marketingName"] == "iPhone 17 Pro Max"


def test_unknown_model_says_so_instead_of_making_a_name_up():
    out = build_payload({"ProductType": "iPhone99,9"}, None, None)
    assert out["marketingName"] is None
    assert any("مدل" in note for note in out["notes"])


def test_only_the_wanted_keys_leave_the_bridge():
    noisy = {
        **VALUES,
        "DevicePublicKey": "----BEGIN...",
        "WiFiAddress": "aa:bb:cc:dd:ee:ff",
        "BluetoothAddress": "aa:bb:cc:dd:ee:f0",
    }
    wanted = {key: noisy.get(key) for key in LOCKDOWN_KEYS}
    out = build_payload(wanted, DISK, BATTERY)
    flat = repr(out)
    assert "aa:bb:cc" not in flat, "مک‌آدرس نباید بیرون برود"
    assert "BEGIN" not in flat, "کلید عمومی دستگاه نباید بیرون برود"


class TestBattery:
    def test_health_uses_nominal_capacity_and_says_so(self):
        out = battery_from_ioregistry(BATTERY)
        assert out["healthPercent"] == 94  # 4400 / 4685
        assert out["basis"] == "NominalChargeCapacity"
        assert out["cycleCount"] == 132
        assert out["currentPercent"] == 78

    def test_falls_back_to_raw_capacity_on_older_ios(self):
        out = battery_from_ioregistry({"DesignCapacity": 4685, "AppleRawMaxCapacity": 4402})
        assert out["basis"] == "AppleRawMaxCapacity"
        assert out["healthPercent"] == 94

    def test_no_design_capacity_means_no_percentage(self):
        # درصدی که مخرجش معلوم نیست، عدد نیست — حدس است
        out = battery_from_ioregistry({"NominalChargeCapacity": 4400, "CycleCount": 12})
        assert out["healthPercent"] is None
        assert out["cycleCount"] == 12

    def test_a_brand_new_battery_is_capped_at_a_hundred(self):
        out = battery_from_ioregistry({"DesignCapacity": 4000, "NominalChargeCapacity": 4080})
        assert out["healthPercent"] == 100

    def test_nonsense_numbers_are_refused(self):
        # ظرفیتی نود برابر طراحی یعنی عددها به هم نمی‌خورند؛ درصد ساخته
        # نمی‌شود ولی چیزی که مستقل و سالم است (تعداد شارژ) می‌ماند
        out = battery_from_ioregistry(
            {"DesignCapacity": 100, "NominalChargeCapacity": 9000, "CycleCount": 12}
        )
        assert out["healthPercent"] is None
        assert out["cycleCount"] == 12

    def test_when_nothing_is_usable_there_is_no_battery_section(self):
        assert battery_from_ioregistry({"DesignCapacity": 100, "NominalChargeCapacity": 9000}) is None

    def test_nothing_readable_returns_nothing(self):
        assert battery_from_ioregistry(None) is None
        assert battery_from_ioregistry({}) is None


class TestPartNumber:
    def test_joins_model_and_region(self):
        assert part_number("MFYM4", "ZA/A") == "MFYM4ZA/A"

    def test_does_not_double_a_region_already_there(self):
        assert part_number("MFYM4ZA", "ZA/A") == "MFYM4ZA/A"

    def test_half_the_pieces_gives_what_is_known(self):
        assert part_number("MFYM4", None) == "MFYM4"
        assert part_number(None, "ZA/A") is None


class TestCapacity:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (251_000_000_000, 256),
            (127_920_000_000, 128),
            (511_000_000_000, 512),
            (1_000_000_000_000, 1024),
            (63_000_000_000, 64),
        ],
    )
    def test_real_disk_sizes_map_to_what_is_sold(self, raw, expected):
        assert marketing_capacity_gb(raw) == expected

    def test_a_size_apple_never_sold_is_refused(self):
        assert marketing_capacity_gb(300_000_000_000) is None
        assert marketing_capacity_gb(0) is None
        assert marketing_capacity_gb(None) is None
        assert marketing_capacity_gb("nonsense") is None


class TestMarketingNames:
    @pytest.mark.parametrize(
        "product_type,name",
        [
            ("iPhone18,2", "iPhone 17 Pro Max"),
            ("iPhone18,1", "iPhone 17 Pro"),
            ("iPhone18,3", "iPhone 17"),
            ("iPhone18,4", "iPhone Air"),
            ("iPhone17,2", "iPhone 16 Pro Max"),
            ("iPhone14,3", "iPhone 13 Pro Max"),
        ],
    )
    def test_known_models(self, product_type, name):
        assert marketing_name(product_type) == name

    def test_unknown_stays_unknown(self):
        assert marketing_name("iPhone99,9") is None
        assert marketing_name(None) is None
        assert marketing_name("") is None
