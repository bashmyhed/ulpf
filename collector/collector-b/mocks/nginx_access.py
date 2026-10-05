#!/usr/bin/env python3
"""Nginx access log JSON emulator - streams continuously."""
import random, time, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

PATHS = ["/", "/api/login", "/api/users", "/api/data", "/health", "/admin", "/static/app.js", "/api/v1/orders"]
METHODS = ["GET", "POST", "PUT", "DELETE"]
UAS = ["Mozilla/5.0", "curl/7.64.1", "PostmanRuntime/7.32.1", "python-requests/2.31.0"]

def gen_nginx():
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    method = random.choice(METHODS)
    path = random.choice(PATHS)
    status = 200 if random.random() < 0.85 else (404 if random.random() < 0.5 else 500)
    bytes_sent = random.randint(100, 50000)
    ua = random.choice(UAS)
    return json.dumps({
        "timestamp": ts,
        "remote_addr": ip,
        "request_method": method,
        "request_path": path,
        "status": status,
        "body_bytes_sent": bytes_sent,
        "http_user_agent": ua,
        "http_referer": "-",
        "request_time": round(random.uniform(0.001, 2.5), 3),
        "upstream_response_time": round(random.uniform(0.001, 1.5), 3),
    })

def main():
    args = parse_args("Nginx access log JSON emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_nginx())
    else:
        streamer = LogStreamer(gen_nginx, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="nginx")
        if not getattr(args, "quiet", False):
            print(f"[nginx_access] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[nginx_access] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[nginx_access] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
