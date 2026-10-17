"""راه‌اندازهای شرکت‌های پرداخت.

هر شرکتِ عضوِ شاپرک (به‌پرداخت، سپ، پاسارگاد، ایران‌کیش، سداد…) شیوه‌ی ارسالِ مبلغِ خودش را دارد و مستندش را خودِ
شرکت به پذیرنده می‌دهد (درخواستِ «اتصالِ نرم‌افزارِ فروشگاه به کارتخوان»). شرکتِ تازه = یک کلاس این‌جا با نامِ همان
کلیدِ `POS_PSP` در `src/lib/enums.ts`، و یک خط در `DRIVERS`. بقیه‌ی پل و برنامه دست نمی‌خورد.

⛔ تا راه‌اندازِ یک شرکت نوشته نشده، پاسخش «رد — هنوز وصل نیست» است، نه «نامعلوم»: چیزی به دستگاه نرفته، پس پولی هم
   نرفته. «نامعلوم» فقط وقتی است که مبلغ رفته و جوابش نیامده.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Job:
    id: int
    psp: str
    host: str | None
    port: int | None
    terminal: str | None
    merchant: str | None
    #: ریال
    amount: int


@dataclass
class Result:
    #: APPROVED | DECLINED | UNKNOWN
    status: str
    trace: str | None = None
    rrn: str | None = None
    card: str | None = None
    message: str | None = None
    #: ریالی که دستگاه واقعاً گرفت، اگر فرق داشت
    amount: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_json(self, job_id: int) -> dict[str, Any]:
        out: dict[str, Any] = {"id": job_id, "status": self.status}
        for key in ("trace", "rrn", "card", "message", "amount"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.raw:
            out["raw"] = self.raw
        return out


Driver = Callable[[Job], Result]


def not_connected(job: Job) -> Result:
    return Result(
        status="DECLINED",
        message="راه‌اندازِ این شرکتِ پرداخت هنوز در پل نیست؛ مبلغی به دستگاه نرفت.",
    )


#: کلید = `POS_PSP`؛ هر شرکتی که این‌جا نیست به `not_connected` می‌رسد
DRIVERS: dict[str, Driver] = {}


def driver_for(psp: str) -> Driver:
    return DRIVERS.get(psp, not_connected)
