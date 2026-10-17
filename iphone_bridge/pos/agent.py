"""حلقه‌ی پرسیدن از سرور. یک کار در هر لحظه — دستگاهِ کارتخوان هم یک مشتری در هر لحظه دارد."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from ..console import say
from .drivers import Job, Result, driver_for

POLL_SECONDS = 1.5
#: سرور در دسترس نبود: کمی صبر، نه پرسیدنِ پشتِ سرِ هم
BACKOFF_SECONDS = 10.0


class Agent:
    def __init__(self, server: str, token: str, opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self.url = server.rstrip("/") + "/api/pos/agent"
        self.token = token.strip()
        self._open = opener

    def _request(self, method: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with self._open(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def next_job(self) -> Job | None:
        body = self._request("GET")
        raw = body.get("job")
        if not raw:
            return None
        return Job(
            id=int(raw["id"]),
            psp=str(raw["psp"]),
            host=raw.get("host"),
            port=raw.get("port"),
            terminal=raw.get("terminal"),
            merchant=raw.get("merchant"),
            amount=int(raw["amount"]),
        )

    def run_job(self, job: Job) -> Result:
        try:
            return driver_for(job.psp)(job)
        except Exception as exc:  # noqa: BLE001 - هر خطای راه‌انداز = «نامعلوم»؛ شاید مبلغ رفته باشد
            return Result(status="UNKNOWN", message=f"خطای پل: {type(exc).__name__}")

    def report(self, job: Job, result: Result) -> None:
        self._request("POST", result.to_json(job.id))

    def once(self) -> bool:
        """یک دور؛ True یعنی کاری انجام شد"""
        job = self.next_job()
        if not job:
            return False
        say(f"POS job {job.id}: {job.psp} {job.amount} rial -> {job.host or '-'}")
        result = self.run_job(job)
        # پاسخ باید برسد — چند بار تلاش، چون پول ممکن است رفته باشد
        for attempt in range(5):
            try:
                self.report(job, result)
                break
            except (urllib.error.URLError, OSError):
                time.sleep(2 * (attempt + 1))
        say(f"POS job {job.id}: {result.status}")
        return True

    def loop(self, stop: threading.Event) -> None:
        say(f"POS agent polling {self.url}")
        while not stop.is_set():
            try:
                worked = self.once()
                stop.wait(0.2 if worked else POLL_SECONDS)
            except urllib.error.HTTPError as err:
                say(f"POS agent: server said {err.code}" + (" (check --pos-token)" if err.code == 401 else ""))
                stop.wait(BACKOFF_SECONDS * (6 if err.code == 401 else 1))
            except (urllib.error.URLError, OSError, ValueError) as err:
                say(f"POS agent: server unreachable ({type(err).__name__}), retrying")
                stop.wait(BACKOFF_SECONDS)


def run_agent_thread(server: str, token: str) -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=Agent(server, token).loop, args=(stop,), daemon=True, name="pos-agent").start()
    return stop
