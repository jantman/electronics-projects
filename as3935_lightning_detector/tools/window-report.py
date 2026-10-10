#!/usr/bin/env python3
"""
window-report.py -- did each scheduled false-lightning window fire, day by day?

The scoring instrument for docs/attic-interference-hunt.md. Everything it reads
is already recorded continuously, so no survey has to be running:

  * strikes (INT_L) -- lightning-bridge's per-strike JSON lines in Loki,
    lossless, with (boot, seq). inject.sh test events are dropped.
  * disturbers and noise-floor interrupts -- the node's own INFO log lines,
    which Home Assistant forwards into its log (the ESPHome integration's
    subscribe_logs option, on since 2026-10-10 ~09:00; nothing before that).
  * pipeline health -- lightning_node_status, lightning_bridge_mqtt_connected
    and up{job="lightning"} must all hold 1 across a window, or a quiet window
    proves nothing (notebook 11.7). Flagged per window.
  * oven sessions -- the Emporia oven circuits, the one source already found
    (notebook 11.11), so its events are not mistaken for the scheduled ones.

    ./window-report.py                    # today and yesterday, local time
    ./window-report.py --from 2026-10-06 --to 2026-10-10
    ./window-report.py --pad 10           # widen each window (minutes)

A window "fires" if any strike lands in it. Disturbers and noise are shown
alongside because a window can disturb the sensor without producing an INT_L.
Standard library only.
"""
import argparse
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
LOKI = "http://prometheus.jasonantman.com:3100"
PROM = "http://prometheus.jasonantman.com:9090"
BRIDGE = '{unit="docker-lightning-bridge.service"} |= "\\"class\\""'
NODELOG = '{unit="docker-hass.service"} |= "esp32-lightning-sensor: ["'

#: (name, start HH:MM, end HH:MM), local time, before --pad. From notebook 11.11.
WINDOWS = [
    ("00:36", "00:34", "00:48"),
    ("04:10", "04:08", "04:55"),   # 04:30-04:52 until 10-05, 04:10 since
    ("12:10", "12:08", "12:28"),   # sometimes :25
    ("18:00", "17:54", "18:07"),
    ("20:10", "20:08", "20:28"),   # sometimes :25
]
OVEN_W = 500  # oven circuits above this are "on"


def get(url, **params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=60) as r:
        return json.load(r)


def loki(query, start, end):
    """All lines in [start, end), paging forward past Loki's per-query limit."""
    out, s = [], int(start.timestamp() * 1e9)
    e = int(end.timestamp() * 1e9)
    while s < e:
        res = get(LOKI + "/loki/api/v1/query_range", query=query, start=s, end=e,
                  limit=5000, direction="forward")["data"]["result"]
        vals = sorted(v for st in res for v in st["values"])
        out += vals
        if len(vals) < 5000:
            break
        s = int(vals[-1][0]) + 1
    return out


def prom_range(query, start, end, step=30):
    out, s = [], start.timestamp()
    while s < end.timestamp():
        e = min(s + step * 10000, end.timestamp())
        for r in get(PROM + "/api/v1/query_range", query=query, start=s, end=e,
                     step=step)["data"]["result"]:
            out += [(t, float(v)) for t, v in r["values"]]
        s = e
    return sorted(out)


def injected(ev):
    up = ev.get("uptime_ms", 0)
    return 84512000 <= up <= 84513000 or (
        ev.get("energy") == 48210 and ev.get("distance_code") == 12 and up <= 100000)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    today = dt.datetime.now(TZ).date()
    ap.add_argument("--from", dest="frm", default=str(today - dt.timedelta(days=1)))
    ap.add_argument("--to", default=str(today), help="inclusive (default: today)")
    ap.add_argument("--pad", type=float, default=0, help="minutes added to each side of every window")
    a = ap.parse_args()
    d0 = dt.date.fromisoformat(a.frm)
    d1 = dt.date.fromisoformat(a.to)
    start = dt.datetime.combine(d0, dt.time(), TZ)
    end = min(dt.datetime.combine(d1 + dt.timedelta(days=1), dt.time(), TZ), dt.datetime.now(TZ))

    strikes, seen = [], set()
    for _, line in loki(BRIDGE, start, end):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("class") != "lightning" or injected(ev) or (ev["boot"], ev["seq"]) in seen:
            continue
        seen.add((ev["boot"], ev["seq"]))
        ev["t"] = dt.datetime.fromisoformat(ev["ts"].replace("Z", "+00:00")).astimezone(TZ)
        strikes.append(ev)

    other = []  # (time, 'D' disturber | 'N' noise)
    for ns, line in loki(NODELOG, start, end):
        kind = "D" if "Disturber" in line else "N" if re.search(r"[Nn]oise", line) else None
        if kind:
            other.append((dt.datetime.fromtimestamp(int(ns) / 1e9, TZ), kind))
    logs_from = min((t for t, _ in other), default=None)

    health = prom_range('min(lightning_node_status) * min(lightning_bridge_mqtt_connected)'
                        ' * min(up{job="lightning"})', start, end)
    oven = prom_range('sum(hass_sensor_power_w{entity=~"sensor.emporia_energy_oven[24]_power"})',
                      start, end)

    def health_ok(ws, we):
        pts = [v for t, v in health if ws.timestamp() <= t <= we.timestamp()]
        return "?" if not pts else ("ok" if min(pts) >= 1 else "DOWN")

    # oven sessions: contiguous runs above OVEN_W, merged across gaps < 10 min
    sessions, cur = [], None
    for t, v in oven:
        if v > OVEN_W:
            if cur and t - cur[1] <= 600:
                cur[1] = t
            else:
                cur = [t, t]
                sessions.append(cur)
    pad = dt.timedelta(minutes=a.pad)
    print(f"{'date':10} {'window':6} {'strikes':>7}  {'D':>3} {'N':>3}  health  detail")
    day = d0
    while day <= d1:
        for name, s, e in WINDOWS:
            ws = dt.datetime.combine(day, dt.time.fromisoformat(s), TZ) - pad
            we = dt.datetime.combine(day, dt.time.fromisoformat(e), TZ) + pad
            if ws > dt.datetime.now(TZ):
                continue
            hits = [x for x in strikes if ws <= x["t"] <= we]
            dn = [k for t, k in other if ws <= t <= we]
            detail = ""
            if hits:
                detail = (f"{hits[0]['t']:%H:%M:%S} seq {hits[0]['boot']}:{hits[0]['seq']}"
                          f"-{hits[-1]['seq']} codes {[x['distance_code'] for x in hits]}")
            logs = "" if logs_from and ws >= logs_from else " (no D/N logs yet)"
            if any(s0 <= we.timestamp() and ws.timestamp() <= e0 for s0, e0 in sessions):
                logs += "  OVEN ON -- not attributable"
            print(f"{day} {name:6} {len(hits):7d}  {dn.count('D'):3d} {dn.count('N'):3d}"
                  f"  {health_ok(ws, we):6}  {detail}{logs}")
        day += dt.timedelta(days=1)

    if sessions:
        print("\noven sessions (the known source -- notebook 11.11):")
    for s, e in sessions:
        n = sum(1 for x in strikes if s - 120 <= x["t"].timestamp() <= e + 120)
        print(f"  {dt.datetime.fromtimestamp(s, TZ):%m-%d %H:%M}-{dt.datetime.fromtimestamp(e, TZ):%H:%M}"
              f"  strikes {n}")

    def anywhere(x):
        t = x["t"]
        return any(dt.datetime.combine(t.date(), dt.time.fromisoformat(s), TZ) - pad <= t
                   <= dt.datetime.combine(t.date(), dt.time.fromisoformat(e), TZ) + pad
                   for _, s, e in WINDOWS)
    stray = [x for x in strikes if not anywhere(x)
             and not any(s - 120 <= x["t"].timestamp() <= e + 120 for s, e in sessions)]
    print(f"\n{len(strikes)} strikes in range; {len(stray)} outside every window and oven session"
          + (":" if stray else "."))
    for x in stray:
        print(f"  {x['t']:%m-%d %H:%M:%S} seq {x['boot']}:{x['seq']} code {x['distance_code']} "
              f"energy {x['energy']}")


if __name__ == "__main__":
    main()
