#!/usr/bin/env python3
"""Cisco ASA syslog emulator - streams continuously."""
import random, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

TEMPLATES = [
    (106001, 106099, "4", "Inbound TCP connection denied from %s/%s to %s/%s flags %s on interface %s"),
    (106100, 106199, "3", "access-list %s permitted %s %s:%s -> %s:%s hits=%s"),
    (106200, 106299, "3", "access-list %s denied %s %s:%s -> %s:%s hits=%s"),
    (106300, 106399, "4", "Deny inbound UDP from %s/%s to %s/%s on interface %s"),
    (106400, 106499, "4", "Deny inbound ICMP from %s to %s on interface %s"),
    (106500, 106599, "3", "Deny TCP (no connection) from %s/%s to %s/%s flags %s on interface %s"),
    (106600, 106699, "4", "Deny protocol %s from %s/%s to %s/%s on interface %s"),
    (106700, 106799, "3", "access-list %s permitted %s %s:%s -> %s:%s hits=%s"),
    (106800, 106899, "3", "access-list %s denied %s %s:%s -> %s:%s hits=%s"),
    (106900, 106983, "3", "reboot"),
]

def get_msg_id(r):
    idx = random.randint(0, len(TEMPLATES) - 1)
    lo, hi, sev, fmt = TEMPLATES[idx]
    if lo == hi:
        return lo, sev, fmt
    return random.randint(lo, hi), sev, fmt

def format_msg(fmt):
    if "reboot" in fmt:
        return fmt
    count = fmt.count("%s")
    args = []
    for _ in range(count):
        r = random.random()
        if r < 0.3:
            args.append(f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}")
        elif r < 0.5:
            args.append(str(random.randint(1024, 65535)))
        elif r < 0.7:
            args.append(random.choice(["TCP", "UDP", "ICMP", "IP", "HTTP", "DNS", "SSH", "FTP"]))
        elif r < 0.85:
            args.append(f"acl-{random.randint(1,100)}")
        else:
            args.append(str(random.randint(1, 10000)))
    return fmt % tuple(args)

def gen_asa():
    msg_id, sev, fmt = get_msg_id(random)
    msg = format_msg(fmt)
    return f"%ASA-{sev}-{msg_id}: {msg}"

def main():
    args = parse_args("Cisco ASA syslog emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_asa())
    else:
        streamer = LogStreamer(gen_asa, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="cisco-asa")
        if not getattr(args, "quiet", False):
            print(f"[cisco_asa] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[cisco_asa] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[cisco_asa] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
