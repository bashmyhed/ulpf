#!/usr/bin/env python3
"""IBM QRadar LEEF log emulator - streams continuously."""
import random, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

EVENTS = [
    ("1001", "High", "Login Success"),
    ("1002", "Medium", "Port Scan Detected"),
    ("1003", "Low", "Connection Allowed"),
    ("1004", "Critical", "Malware Detected"),
    ("1005", "High", "Policy Violation"),
    ("1006", "Medium", "Anomalous Traffic"),
    ("1007", "Low", "DNS Query"),
    ("1008", "High", "Brute Force Attempt"),
]

def gen_leef():
    ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    src = f"192.168.1.{random.randint(100,200)}"
    dst = f"10.0.0.{random.randint(1,50)}"
    user = random.choice(["admin", "user1", "user2", "user3", "root"])
    event_id, sev, action = random.choice(EVENTS)
    header = f"LEEF:1.0|IBM|QRadar|7.5.0|{event_id}|"
    fields = [
        f"devTime={ts}",
        f"src={src}",
        f"dst={dst}",
        f"suser={user}",
        f"action={action}",
        f"severity={sev}",
        f"cat=Security",
        f"msg=Event {event_id} detected",
    ]
    return header + "\t".join(fields)

def main():
    args = parse_args("IBM QRadar LEEF emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_leef())
    else:
        streamer = LogStreamer(gen_leef, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="qradar-leef")
        if not getattr(args, "quiet", False):
            print(f"[leef_qradar] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[leef_qradar] Press Ctrl+C to stop", file=sys.stderr)
        try:
            streamer.start()
            if args.duration > 0:
                time.sleep(args.duration)
            else:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            streamer.stop()
            if not getattr(args, "quiet", False):
                print(f"\n[leef_qradar] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
