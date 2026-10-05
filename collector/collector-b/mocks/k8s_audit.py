#!/usr/bin/env python3
"""Kubernetes audit log JSON emulator - streams continuously."""
import random, time, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

USERS = ["admin", "developer", "system:serviceaccount:default:deployer"]
VERBS = ["get", "list", "create", "update", "delete", "patch"]
RESOURCES = ["pods", "services", "deployments", "secrets", "configmaps"]
NAMESPACES = ["default", "kube-system", "production", "staging"]

def gen_k8s():
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    user = random.choice(USERS)
    verb = random.choice(VERBS)
    resource = random.choice(RESOURCES)
    ns = random.choice(NAMESPACES)
    code = 200 if random.random() < 0.9 else (403 if random.random() < 0.5 else 404)
    return json.dumps({
        "kind": "Event",
        "apiVersion": "audit.k8s.io/v1",
        "level": "RequestResponse",
        "auditID": f"{random.randint(10**18, 10**19-1):018x}",
        "stage": "ResponseComplete",
        "requestURI": f"/api/v1/namespaces/{ns}/{resource}",
        "verb": verb,
        "user": {
            "username": user,
            "uid": f"user-{random.randint(1000,9999)}",
            "groups": ["system:authenticated"]
        },
        "sourceIPs": [f"10.0.{random.randint(0,255)}.{random.randint(1,254)}"],
        "userAgent": "kubectl/v1.28.0",
        "objectRef": {
            "resource": resource,
            "namespace": ns,
            "name": f"pod-{random.randint(1000,9999)}",
            "apiVersion": "v1"
        },
        "responseStatus": {"metadata": {}, "code": code},
        "requestReceivedTimestamp": ts,
        "stageTimestamp": ts,
    })

def main():
    args = parse_args("Kubernetes audit log JSON emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_k8s())
    else:
        streamer = LogStreamer(gen_k8s, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="k8s-audit")
        if not getattr(args, "quiet", False):
            print(f"[k8s_audit] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[k8s_audit] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[k8s_audit] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
