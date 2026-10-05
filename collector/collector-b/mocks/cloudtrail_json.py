#!/usr/bin/env python3
"""AWS CloudTrail JSON log emulator - streams continuously."""
import random, time, json, sys, os, uuid
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

USERS = ["admin", "developer", "analyst", "deployer", "readonly"]
EVENTS = [
    ("ec2.amazonaws.com", "StartInstances", "us-east-1"),
    ("ec2.amazonaws.com", "StopInstances", "us-east-1"),
    ("iam.amazonaws.com", "CreateUser", "us-east-1"),
    ("iam.amazonaws.com", "AddUserToGroup", "us-east-1"),
    ("s3.amazonaws.com", "PutObject", "us-east-1"),
    ("sts.amazonaws.com", "AssumeRole", "us-east-1"),
    ("kms.amazonaws.com", "ListKeys", "us-east-1"),
    ("cloudtrail.amazonaws.com", "StartLogging", "us-east-1"),
]

def gen_cloudtrail():
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    user = random.choice(USERS)
    source, event, region = random.choice(EVENTS)
    ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    e = {
        "eventVersion": "1.08",
        "userIdentity": {
            "type": "IAMUser",
            "principalId": f"AIDA{random.randint(100000000000,999999999999)}",
            "arn": f"arn:aws:iam::123456789012:user/{user}",
            "accountId": "123456789012",
            "accessKeyId": f"AKIA{random.randint(100000000000,999999999999)}",
            "userName": user,
            "sessionContext": {"attributes": {"creationDate": ts, "mfaAuthenticated": "false"}}
        },
        "eventTime": ts,
        "eventSource": source,
        "eventName": event,
        "awsRegion": region,
        "sourceIPAddress": ip,
        "userAgent": "aws-cli/2.13.5 Python/3.11.4",
        "requestParameters": {},
        "responseElements": None,
        "requestID": str(uuid.uuid4()),
        "eventID": str(uuid.uuid4()),
        "readOnly": False,
        "eventType": "AwsApiCall",
        "managementEvent": True,
        "recipientAccountId": "123456789012",
        "eventCategory": "Management",
        "tlsDetails": {"tlsVersion": "TLSv1.2", "cipherSuite": "ECDHE-RSA-AES128-GCM-SHA256"}
    }
    if random.random() < 0.05:
        e["errorCode"] = "AccessDenied"
        e["errorMessage"] = "User is not authorized to perform this action"
    return json.dumps(e)

def main():
    args = parse_args("AWS CloudTrail JSON emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_cloudtrail())
    else:
        streamer = LogStreamer(gen_cloudtrail, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="aws-cloudtrail")
        if not getattr(args, "quiet", False):
            print(f"[cloudtrail_json] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[cloudtrail_json] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[cloudtrail_json] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
