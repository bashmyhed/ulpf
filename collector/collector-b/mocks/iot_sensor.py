#!/usr/bin/env python3
"""IoT sensor telemetry JSON emulator - streams continuously."""
import random, time, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

DEVICES = [f"SENSOR-{i:03d}" for i in range(1, 11)]
SENSORS = [
    ("temperature", "C", 15, 35),
    ("humidity", "%", 30, 80),
    ("pressure", "hPa", 980, 1020),
    ("co2", "ppm", 400, 2000),
    ("light", "lux", 0, 10000),
]

def gen_iot():
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    device = random.choice(DEVICES)
    sensor_type, unit, min_val, max_val = random.choice(SENSORS)
    value = round(random.uniform(min_val, max_val), 2)
    status = "ok" if random.random() < 0.95 else ("warning" if random.random() < 0.5 else "error")
    return json.dumps({
        "timestamp": ts,
        "device_id": device,
        "sensor_type": sensor_type,
        "value": value,
        "unit": unit,
        "status": status,
        "location": {
            "lat": round(random.uniform(-90, 90), 6),
            "lon": round(random.uniform(-180, 180), 6)
        },
        "battery": random.randint(0, 100),
        "firmware": "1.2.3"
    })

def main():
    args = parse_args("IoT sensor telemetry JSON emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_iot())
    else:
        streamer = LogStreamer(gen_iot, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="iot-sensor")
        if not getattr(args, "quiet", False):
            print(f"[iot_sensor] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[iot_sensor] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[iot_sensor] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
