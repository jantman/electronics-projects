#!/usr/bin/env python3
"""
ws-log-bridge.py -- stream a node's logs from the ESPHome Device Builder
dashboard to stdout, for `ambient-survey.py --stdin`.

Exists because ESPHome does not run on the workstation: it runs on a server
behind the dashboard, so the usual `esphome logs ... | ambient-survey.py --stdin`
pipe has nothing to call. The dashboard can stream a node's logs itself; this
speaks its websocket protocol and prints one log line per line.

    ./ws-log-bridge.py --cafile ca.pem | ./ambient-survey.py --stdin --minutes 60

Needs `pip install websockets`, and an entry in ~/.netrc for the dashboard host
holding the same username and password as the dashboard's own sign-in page:

    machine esphome.example.com login USER password PASS

Validated against serial on 2026-09-13: a serial survey and a survey through
this bridge, run side by side while the SEN-39002 emulator fired 15 bursts,
counted 15 disturbers each, and every line the bridge forwarded was read.

Protocol, reverse-engineered from the dashboard's own JS bundle (server 1.1.0,
ESPHome 2026.6):
  wss://HOST:PORT/ws   the server opens with a hello carrying requires_auth
  -> {"command": "auth/login",   "message_id": "1", "args": {username, password}}
  -> {"command": "devices/logs", "message_id": "2", "args": {configuration, "port": "OTA"}}
  <- {"message_id": "2", "event": "output", "data": "<exactly one log line>"}
     ... until {"event": "result"}, or {"error_code": ...}
Two traps:
  * message_id MUST be a string. An integer id is dropped without any reply --
    the login simply hangs, which looks exactly like a credentials problem.
  * each output event is one line with NO trailing newline, and ANSI escapes
    arrive as the literal four characters \\033. Both are fixed up here.
Exactly one login attempt is made: the dashboard rate-limits failed sign-ins.
"""
import argparse
import asyncio
import base64
import json
import netrc
import re
import ssl
import sys
import time

try:
    import websockets
except ImportError:
    sys.exit("websockets not installed:  pip install websockets")

# At logger level VERBOSE, ESPHome prints the WiFi password in plain text when a
# client connects. Never forward it.
PASSWORD = re.compile(r"(Password: )'[^']*'")


def err(*msg):
    print("[bridge]", *msg, file=sys.stderr, flush=True)


async def bridge(args, user, pw):
    hdr = {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}
    ctx = ssl.create_default_context(cafile=args.cafile)  # None -> system trust store
    url = f"wss://{args.host}:{args.port}/ws"
    async with websockets.connect(url, ssl=ctx, additional_headers=hdr,
                                  max_size=None, open_timeout=20) as ws:
        await asyncio.wait_for(ws.recv(), 20)  # hello
        await ws.send(json.dumps({"command": "auth/login", "message_id": "1",
                                  "args": {"username": user, "password": pw}}))
        while True:
            reply = json.loads(await asyncio.wait_for(ws.recv(), 15))
            if reply.get("message_id") == "1":
                break
        if "error_code" in reply or not isinstance(reply.get("result"), dict):
            err("login failed, not retrying:", reply.get("error_code"), reply.get("details"))
            return 2

        await ws.send(json.dumps({"command": "devices/logs", "message_id": "2",
                                  "args": {"configuration": args.config, "port": "OTA"}}))
        err("streaming", args.config)
        start, forwarded = time.time(), 0
        try:
            while not args.max_seconds or time.time() - start < args.max_seconds:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), 1))
                except asyncio.TimeoutError:
                    continue
                if msg.get("message_id") != "2":
                    continue
                if msg.get("event") == "output":
                    line = PASSWORD.sub(r"\1'<redacted>'", str(msg.get("data", "")))
                    sys.stdout.write(line.replace("\\033", "\x1b") + "\n")
                    sys.stdout.flush()
                    forwarded += 1
                elif msg.get("event") == "result" or "error_code" in msg:
                    err("stream ended by the dashboard:", msg.get("error_code") or msg.get("data"))
                    break
        except BrokenPipeError:
            err("reader closed the pipe")  # the survey finished: the normal way out
        except websockets.ConnectionClosed:
            err("dashboard closed the connection")
        finally:
            try:
                await ws.send(json.dumps({"command": "devices/stop_stream", "message_id": "3",
                                          "args": {"stream_id": "2"}}))
            except Exception:
                pass
            err("lines forwarded:", forwarded)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="esphome.jasonantman.com", help="dashboard host (default: %(default)s)")
    ap.add_argument("--port", type=int, default=16052, help="dashboard port (default: %(default)s)")
    ap.add_argument("--config", default="esp32-lightning-sensor.yaml",
                    help="the node's configuration file name on the dashboard (default: %(default)s)")
    ap.add_argument("--cafile", default=None,
                    help="CA certificate that signs the dashboard's TLS cert, if it is not in "
                         "the system trust store")
    ap.add_argument("--max-seconds", type=float, default=0,
                    help="hard stop; 0 = none (default). The survey closing the pipe is the normal end.")
    args = ap.parse_args()

    try:
        auth = netrc.netrc().authenticators(args.host)
    except (FileNotFoundError, netrc.NetrcParseError) as exc:
        sys.exit(f"cannot read ~/.netrc: {exc}")
    if not auth:
        sys.exit(f"no ~/.netrc entry for {args.host}")
    user, _, pw = auth

    try:
        sys.exit(asyncio.run(bridge(args, user, pw)))
    except BrokenPipeError:
        sys.exit(0)


if __name__ == "__main__":
    main()
