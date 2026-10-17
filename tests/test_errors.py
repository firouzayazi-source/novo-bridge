"""ترجمه‌ی خطاها.

هر پیام باید به کاربر بگوید **الان چه کار کند**. آزمون‌ها روی نامِ
کلاس کار می‌کنند، همان‌طور که خودِ `translate` — تا اگر pymobiledevice3
کلاسی را جابه‌جا کرد، پل به پیام عمومی برگردد نه اینکه بترکد.
"""

from __future__ import annotations

import pytest

from iphone_bridge.errors import BridgeError, translate


def fake(name: str, message: str = "", base: type[Exception] = Exception) -> Exception:
    return type(name, (base,), {})(message)


@pytest.mark.parametrize(
    "exception_name,code",
    [
        ("PasswordRequiredError", "locked"),
        ("PairingDialogResponsePendingError", "pairing_pending"),
        ("UserDeniedPairingError", "pairing_denied"),
        ("NotTrustedError", "not_trusted"),
        ("NotPairedError", "not_trusted"),
        ("InvalidHostIDError", "not_trusted"),
        ("NoDeviceConnectedError", "no_device"),
        ("DeviceNotFoundError", "no_device"),
        ("ConnectionFailedToUsbmuxdError", "no_usbmuxd"),
    ],
)
def test_known_failures_become_instructions(exception_name, code):
    err = translate(fake(exception_name))
    assert err.code == code
    assert err.message, "هر خطا باید پیام داشته باشد"


def test_a_locked_phone_tells_the_user_to_unlock_it():
    assert "قفل" in translate(fake("PasswordRequiredError")).message


def test_an_untrusted_phone_names_the_trust_button():
    assert "Trust" in translate(fake("NotTrustedError")).message


def test_missing_apple_service_points_at_itunes():
    assert "iTunes" in translate(fake("ConnectionFailedToUsbmuxdError")).message
    assert "iTunes" in translate(ConnectionRefusedError()).message


def test_an_unknown_failure_still_gets_a_usable_message():
    err = translate(RuntimeError("something deep broke"))
    assert err.code == "unknown"
    assert err.message
    # جزئیات فنی می‌ماند ولی جدا از پیام کاربر
    assert "something deep broke" in (err.detail or "")
    assert "something deep broke" not in err.message


def test_our_own_errors_pass_through_untouched():
    mine = BridgeError(code="custom", message="پیام خودم")
    assert translate(mine) is mine


def test_the_wire_shape_is_what_the_web_app_expects():
    body = translate(fake("PasswordRequiredError")).to_dict()
    assert body["ok"] is False
    assert body["code"] == "locked"
    assert body["retryable"] is True
    assert isinstance(body["error"], str)
