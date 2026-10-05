#!/usr/bin/env python3
"""PostgreSQL CSV log emulator - streams continuously."""
import random, time, sys, os, csv, io
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

USERS = ["postgres", "app_user", "readonly", "admin"]
DBS = ["production", "analytics", "staging"]
QUERIES = [
    "SELECT * FROM users WHERE id = $1",
    "INSERT INTO orders (user_id, amount) VALUES ($1, $2)",
    "UPDATE products SET stock = stock - 1 WHERE id = $1",
    "DELETE FROM sessions WHERE expired < now()",
    "CREATE INDEX idx_users_email ON users(email)",
    "VACUUM ANALYZE orders",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
]

def gen_postgres():
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    pid = random.randint(1000, 99999)
    user = random.choice(USERS)
    db = random.choice(DBS)
    duration = random.randint(1, 5000)
    query = random.choice(QUERIES)
    severity = "LOG" if random.random() < 0.9 else ("ERROR" if random.random() < 0.5 else "WARNING")
    return f"{ts},{pid},{user},{db},{duration},{severity},{query}"

def main():
    args = parse_args("PostgreSQL CSV log emulator")
    random.seed(args.seed)
    if args.count > 0:
        print("timestamp,pid,user,database,duration_ms,severity,query")
        for _ in range(args.count):
            print(gen_postgres())
    else:
        streamer = LogStreamer(gen_postgres, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="postgres")
        if not getattr(args, "quiet", False):
            print(f"[db_postgres] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[db_postgres] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[db_postgres] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
