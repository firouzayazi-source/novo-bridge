"""ترجمه‌ی خطاهای pymobiledevice3 به پیام فارسیِ قابل فهم.

قاعده: کاربر پشت پیشخوان فروشگاه است، نه توسعه‌دهنده. هر پیام باید
بگوید **الان چه کار کند**، نه اینکه کدام استثنا پرتاب شده.

هر خطا یک `code` ماشین‌خوان هم دارد تا رابط وب بتواند بر اساسش تصمیم
بگیرد (مثلاً دکمه‌ی «دوباره امتحان کن» را نشان دهد یا نه)، و پیام فارسی
برای نمایش.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeError(Exception):
    """خطایی که می‌شود همان‌طور به کاربر نشان داد."""

    code: str
    message: str
    """جزئیات فنی — فقط برای عیب‌یابی، نه برای کاربر."""
    detail: str | None = None
    """کاربر با تلاش دوباره (مثلاً بعد از باز کردن قفل) شانس دارد؟"""
    retryable: bool = True

    def __str__(self) -> str:  # pragma: no cover - فقط برای لاگ
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "ok": False,
            "code": self.code,
            "error": self.message,
            "retryable": self.retryable,
        }
        if self.detail:
            out["detail"] = self.detail
        return out


NO_DEVICE = BridgeError(
    code="no_device",
    message="گوشی وصل نیست. کابل را به کامپیوتر بزنید.",
)

NO_USBMUXD = BridgeError(
    code="no_usbmuxd",
    message=(
        "سرویس اپل روی این کامپیوتر اجرا نیست. "
        "iTunes یا Apple Devices را نصب کنید و کامپیوتر را یک بار ری‌استارت کنید."
    ),
)

APPLE_NOT_LISTENING = BridgeError(
    code="no_usbmuxd",
    message=(
        "برنامه‌ی اپل روی این کامپیوتر هست ولی سرویسِ اتصالش جواب نمی‌دهد. "
        "Apple Devices را کامل ببندید و دوباره باز کنید؛ اگر نشد کامپیوتر را یک بار ری‌استارت کنید."
    ),
)

LOCKED = BridgeError(
    code="locked",
    message="گوشی قفل است. قفلش را باز کنید و دوباره بزنید.",
)

NOT_TRUSTED = BridgeError(
    code="not_trusted",
    message=(
        "گوشی به این کامپیوتر اعتماد نکرده. قفل گوشی را باز کنید، "
        "روی پیغام «Trust This Computer» تأیید بزنید و دوباره امتحان کنید."
    ),
)

PAIRING_PENDING = BridgeError(
    code="pairing_pending",
    message="روی گوشی پیغام «Trust» آمده — تأییدش کنید و دوباره بزنید.",
)

PAIRING_DENIED = BridgeError(
    code="pairing_denied",
    message=(
        "روی گوشی «Don't Trust» زده شده. کابل را جدا و دوباره وصل کنید "
        "و این بار Trust را بزنید."
    ),
)


def _module_path(exc: BaseException) -> str:
    cls = type(exc)
    return f"{cls.__module__}.{cls.__qualname__}"


def translate(exc: BaseException) -> BridgeError:
    """هر استثنایی → خطای قابل نمایش.

    بر اساس **نام کلاس** تصمیم می‌گیرد نه ایمپورت مستقیم، تا اگر
    pymobiledevice3 روزی کلاسی را جابه‌جا یا حذف کرد، پل نترکد و فقط به
    پیام عمومی برگردد.
    """
    if isinstance(exc, BridgeError):
        return exc

    name = type(exc).__name__
    text = str(exc)

    # ترتیب مهم است: خاص‌ها پیش از عام‌ها. مثلاً PasswordRequiredError
    # زیرکلاس PairingError است.
    if name in {"PasswordRequiredError"}:
        return LOCKED
    if name in {"PairingDialogResponsePendingError"}:
        return PAIRING_PENDING
    if name in {"UserDeniedPairingError"}:
        return PAIRING_DENIED
    if name in {"NotTrustedError", "NotPairedError", "InvalidHostIDError", "FatalPairingError"}:
        return NOT_TRUSTED
    if name in {"PairingError"}:
        return NOT_TRUSTED
    if name in {"NoDeviceConnectedError", "DeviceNotFoundError", "ConnectionFailedError"}:
        return NO_DEVICE
    if name in {"ConnectionFailedToUsbmuxdError", "MuxException", "MuxVersionError"}:
        return NO_USBMUXD

    # usbmuxd روی ویندوز یک سرویس ویندوزی است که با iTunes می‌آید؛ نبودنش
    # به شکل خطای سوکت درمی‌آید، نه استثنای خودِ کتابخانه
    if isinstance(exc, (ConnectionRefusedError, FileNotFoundError)):
        return NO_USBMUXD
    if isinstance(exc, (TimeoutError, OSError)) and "usbmux" in text.lower():
        return NO_USBMUXD

    return BridgeError(
        code="unknown",
        message="خواندن گوشی نشد. کابل را جدا و دوباره وصل کنید.",
        detail=f"{_module_path(exc)}: {text}"[:400],
    )
