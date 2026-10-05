#!/usr/bin/env python3
"""Palo Alto Networks NGFW CEF log emulator - streams continuously."""
import random, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

def gen_cef():
    ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    src = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    dst = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    spt = random.randint(1024, 65535)
    dpt = random.choice([80, 443, 22, 25, 53, 8080, 8443])
    proto = random.choice(["TCP", "UDP", "ICMP"])
    action = random.choice(["allow", "deny", "drop"])
    rule = f"rule-{random.randint(1,50)}"
    app = random.choice(["web-browsing", "ssl", "ssh", "dns", "smtp", "ftp"])
    bytes_in = random.randint(100, 100000)
    bytes_out = random.randint(100, 50000)
    return (f"CEF:0|PaloAlto|PAN-OS|10.1.0|TRAFFIC|{action}|0|"
            f"rt={ts} src={src} dst={dst} spt={spt} dpt={dpt} "
            f"proto={proto} act={rule} app={app} "
            f"bytes_in={bytes_in} bytes_out={bytes_out}")

def main():
    args = parse_args("Palo Alto NGFW CEF emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_cef())
    else:
        streamer = LogStreamer(gen_cef, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="paloalto-cef")
        if not getattr(args, "quiet", False):
            print(f"[firewall_cef] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[firewall_cef] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[firewall_cef] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
