"""طرفِ پلِ «ارسال به کارتخوان»: پرسیدن، راه‌انداز، پاسخ — بی سرورِ واقعی."""

from __future__ import annotations

import io
import json

from iphone_bridge.pos import DRIVERS, Agent, Job, Result


class FakeServer:
    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.results = []
        self.headers = []

    def __call__(self, request, timeout=0):
        self.headers.append(request.get_header("Authorization"))
        if request.get_method() == "POST":
            self.results.append(json.loads(request.data.decode("utf-8")))
            body = {"ok": True}
        else:
            body = {"ok": True, "job": self.jobs.pop(0) if self.jobs else None}
        return _Resp(json.dumps(body).encode("utf-8"))


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


JOB = {"id": 7, "psp": "BEHPARDAKHT", "host": "192.168.1.50", "port": 1024, "terminal": None, "merchant": None, "amount": 700_000_000}


def test_no_job_does_nothing():
    server = FakeServer([])
    assert Agent("https://x.test/", "t", opener=server).once() is False
    assert server.headers == ["Bearer t"]


def test_unknown_psp_declines_without_touching_device():
    server = FakeServer([dict(JOB, psp="NOBODY")])
    assert Agent("https://x.test", "t", opener=server).once() is True
    assert server.results[0]["status"] == "DECLINED"
    assert server.results[0]["id"] == 7


def test_driver_result_is_reported_in_rial():
    seen = {}

    def fake(job: Job) -> Result:
        seen["amount"] = job.amount
        return Result(status="APPROVED", trace="123456", rrn="987", card="603799******1234")

    DRIVERS["TESTPSP"] = fake
    try:
        server = FakeServer([dict(JOB, psp="TESTPSP")])
        Agent("https://x.test", "t", opener=server).once()
    finally:
        DRIVERS.pop("TESTPSP")
    assert seen["amount"] == 700_000_000
    assert server.results[0] == {"id": 7, "status": "APPROVED", "trace": "123456", "rrn": "987", "card": "603799******1234"}


def test_driver_crash_is_unknown_not_declined():
    def boom(job: Job) -> Result:
        raise ConnectionResetError

    DRIVERS["BOOM"] = boom
    try:
        server = FakeServer([dict(JOB, psp="BOOM")])
        Agent("https://x.test", "t", opener=server).once()
    finally:
        DRIVERS.pop("BOOM")
    assert server.results[0]["status"] == "UNKNOWN"
