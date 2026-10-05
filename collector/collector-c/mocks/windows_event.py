#!/usr/bin/env python3
"""Windows Event Log XML emulator - streams continuously."""
import random, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from log_streamer import LogStreamer, parse_args

EVENTS = [
    (4624, 2, "An account was successfully logged on"),
    (4625, 3, "An account failed to log on"),
    (4634, 2, "An account was logged off"),
    (4648, 2, "A logon was attempted using explicit credentials"),
    (4672, 2, "Special privileges assigned to new logon"),
    (4720, 2, "A user account was created"),
    (4726, 2, "A user account was deleted"),
    (4732, 2, "A member was added to a security-enabled local group"),
]

def gen_windows(multiline=False):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    event_id, level, msg = random.choice(EVENTS)
    guid = f"{random.randint(10**31,10**32-1):032x}"
    rec_id = random.randint(100000,999999)
    pid = random.randint(1000,9999)
    tid = random.randint(1000,9999)
    if multiline:
        return f"""<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
  <System>
    <Provider Name="Microsoft-Windows-Security-Auditing" Guid="{guid}" EventSourceName="Microsoft-Windows-Security-Auditing"/>
    <EventID Qualifiers="16384">{event_id}</EventID>
    <Version>0</Version>
    <Level>{level}</Level>
    <Task>0</Task>
    <Opcode>0</Opcode>
    <Keywords>0x8000000000000000</Keywords>
    <TimeCreated SystemTime="{ts}"/>
    <EventRecordID>{rec_id}</EventRecordID>
    <Correlation/>
    <Execution ProcessID="{pid}" ThreadID="{tid}"/>
    <Channel>Security</Channel>
    <Computer>WIN-SERVER-01</Computer>
    <Security/>
  </System>
  <EventData>
    <Data Name="Message">{msg}</Data>
  </EventData>
</Event>"""
    else:
        return f'<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><Provider Name="Microsoft-Windows-Security-Auditing" Guid="{guid}" EventSourceName="Microsoft-Windows-Security-Auditing"/><EventID Qualifiers="16384">{event_id}</EventID><Version>0</Version><Level>{level}</Level><Task>0</Task><Opcode>0</Opcode><Keywords>0x8000000000000000</Keywords><TimeCreated SystemTime="{ts}"/><EventRecordID>{rec_id}</EventRecordID><Correlation/><Execution ProcessID="{pid}" ThreadID="{tid}"/><Channel>Security</Channel><Computer>WIN-SERVER-01</Computer><Security/></System><EventData><Data Name="Message">{msg}</Data></EventData></Event>'

def main():
    args = parse_args("Windows Event Log XML emulator")
    random.seed(args.seed)
    if args.count > 0:
        for _ in range(args.count):
            print(gen_windows())
    else:
        streamer = LogStreamer(gen_windows, mode=args.mode, target=args.output,
                               rate=args.rate, duration=args.duration, identifier="windows-event")
        if not getattr(args, "quiet", False):
            print(f"[windows_event] Streaming at {args.rate} eps to {args.mode}:{streamer.target}", file=sys.stderr)
            print("[windows_event] Press Ctrl+C to stop", file=sys.stderr)
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
                print(f"\n[windows_event] Sent {streamer.count} events", file=sys.stderr)

if __name__ == "__main__":
    main()
