"""پیدا کردنِ سرویسِ اپل روی ویندوز (۲۸ مهر ۱۴۰۵: «Apple Devices» گوشی را می‌دید، پل می‌گفت سرویس نیست)."""

from __future__ import annotations

from iphone_bridge import usbmux_find as uf

NETSTAT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1100
  TCP    127.0.0.1:5354         0.0.0.0:0              LISTENING       4520
  TCP    127.0.0.1:27016        0.0.0.0:0              LISTENING       7788
  TCP    127.0.0.1:27016        127.0.0.1:50000        ESTABLISHED     7788
  TCP    127.0.0.1:17377        0.0.0.0:0              LISTENING       9000
"""

TASKLIST = '''"svchost.exe","1100","Services","0","10,000 K"
"mDNSResponder.exe","4520","Services","0","5,000 K"
"AppleMobileDeviceProcess.exe","7788","Services","0","20,000 K"
"iPhoneBridge.exe","9000","Console","1","30,000 K"
'''


def test_parse_netstat_only_listening() -> None:
    rows = uf.parse_netstat(NETSTAT)
    assert ("127.0.0.1", 27016, 7788) in rows
    assert all(pid != 7788 or port == 27016 for _, port, pid in rows)
    assert len(rows) == 4


def test_parse_tasklist() -> None:
    names = uf.parse_tasklist(TASKLIST)
    assert names[7788] == "AppleMobileDeviceProcess.exe"
    assert names[9000] == "iPhoneBridge.exe"


def test_apple_ports_picks_only_apple_process() -> None:
    ports, procs = uf.apple_ports(NETSTAT, TASKLIST)
    assert ports == [27016]
    assert procs == ["AppleMobileDeviceProcess.exe"]


def test_no_apple_process() -> None:
    ports, procs = uf.apple_ports(NETSTAT, '"svchost.exe","1100","Services","0","1 K"')
    assert ports == [] and procs == []


def test_found_on_other_port_sets_env(monkeypatch) -> None:
    monkeypatch.delenv(uf.ENV, raising=False)
    monkeypatch.setattr(uf, "_ours", None)
    monkeypatch.setattr(uf.sys, "platform", "win32")
    monkeypatch.setattr(uf, "_open", lambda host, port, timeout=0.5: port == 27016)
    monkeypatch.setattr(uf, "_run", lambda args: NETSTAT if args[0] == "netstat" else TASKLIST)
    found = uf.diagnose()
    assert found.address == "127.0.0.1:27016"
    assert uf.os.environ[uf.ENV] == "127.0.0.1:27016"
    # سرویس رفت → متغیرِ خودمان پاک و از نو گشته می‌شود
    monkeypatch.setattr(uf, "_open", lambda host, port, timeout=0.5: False)
    again = uf.diagnose()
    assert again.address is None
    assert uf.ENV not in uf.os.environ
    assert again.apple_processes == ("AppleMobileDeviceProcess.exe",)


def test_default_port_untouched(monkeypatch) -> None:
    monkeypatch.delenv(uf.ENV, raising=False)
    monkeypatch.setattr(uf, "_open", lambda host, port, timeout=0.5: port == 27015)
    assert uf.diagnose().address == "127.0.0.1:27015"
    assert uf.ENV not in uf.os.environ
