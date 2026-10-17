"""ارسالِ مبلغ به کارتخوان — طرفِ پل (`src/lib/pos.ts` طرفِ برنامه‌ی وب).

پل هر ثانیه و نیم از سرور می‌پرسد «کاری هست؟» (`GET /api/pos/agent`)، مبلغ (ریال) را با راه‌اندازِ همان شرکتِ پرداخت
روی شبکه‌ی مغازه به دستگاه می‌دهد و پاسخ را برمی‌گرداند (`POST`). پل به سرور می‌رود، نه برعکس: هیچ درگاهی در مغازه باز
نمی‌شود و از گوشی هم کار می‌کند.

  iPhoneBridge.exe --pos-server https://novo.stland.ir --pos-token <رمز>

پیام‌های کنسول ASCII‌اند (قاعده‌ی کلِ پل).
"""

from .agent import Agent, run_agent_thread
from .drivers import DRIVERS, Job, Result

__all__ = ["Agent", "DRIVERS", "Job", "Result", "run_agent_thread"]
