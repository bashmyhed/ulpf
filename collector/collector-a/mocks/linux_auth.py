#!/usr/bin/env python3
"""Linux auth.log emulator - streams continuously."""
import random, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

HOSTS = ["web-01", "db-01", "app-01", "mail-01"]
USERS = ["root", "admin", "ubuntu", "deploy", "backup"]

def gen_auth():
    ts = time.strftime("%b %d %H:%M:%S", time.localtime())
    host = random.choice(HOSTS)
    user = random.choice(USERS)
    ip = f"192.168.1.{random.randint(100,200)}"
    r = random.random()
    if r < 0.3:
        msg = f"sshd[12345]: Failed password for {user} from {ip} port {random.randint(1024,65535)} ssh2"
    elif r < 0.5:
        msg = f"sshd[12345]: Accepted password for {user} from {ip} port {random.randint(1024,65535)} ssh2"
    elif r < 0.6:
        msg = f"sshd[12345]: Failed password for invalid user {user} from {ip} port {random.randint(1024,65535)} ssh2"
    elif r < 0.7:
        msg = f"sudo: {user} : TTY=pts/0 ; PWD=/home/{user} ; USER=root ; COMMAND=/bin/bash"
    elif r < 0.8:
        msg = f"su: (to root) {user} on pts/0"
    elif r < 0.9:
        msg = f"sshd[12345]: Connection closed by {ip} port {random.randint(1024,65535)} [preauth]"
    else:
        msg = f"CRON[12345]: (root) CMD (cd / && run-parts /etc/cron.hourly)"
    return f"{ts} {host} {msg}"

def main():
    args = parse_args("Linux auth.log emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_auth())
    else:
        streamer = LogStreamer(gen_auth, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="linux-auth")
        if not getattr(args, "quiet", False):
            print(f"[linux_auth] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[linux_auth] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[linux_auth] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
