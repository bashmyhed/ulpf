#!/usr/bin/env python3
"""Base log streaming infrastructure for emulators."""
import time, random, sys, os, signal, threading, socket, urllib.request, argparse

class LogStreamer:
    """Streams log events to file/stdout/syslog/http/tcp/journald one by one at a configurable rate."""
    
    def __init__(self, generator, mode="file", target=None, rate=10, duration=0, identifier="ulpf-emulator"):
        self.generator = generator
        self.mode = mode.lower() if mode else "file"
        self.rate = rate
        self.duration = duration
        self.identifier = identifier
        self.running = False
        self.count = 0
        self._stop_event = threading.Event()
        self._fh = None
        self._close_fh = False
        self._sock = None
        self._target_addr = None
        self._url = None
        self._sock_path = None
        
        # Intelligent target defaults per mode
        if not target or target == "-":
            if self.mode in ("file", "stdout", "stdio"):
                target = "-"
            elif self.mode == "syslog_udp":
                target = "127.0.0.1:514"
            elif self.mode == "syslog_tcp":
                target = "127.0.0.1:601"
            elif self.mode == "tcp":
                target = "127.0.0.1:5044"
            elif self.mode == "http":
                target = "http://127.0.0.1:8080/"
            elif self.mode in ("journald", "journal"):
                target = "/run/systemd/journal/socket" if os.path.exists("/run/systemd/journal/socket") else "/dev/log"
        self.target = target
        
        # Setup transport
        if self.mode in ("file", "stdout", "stdio"):
            if self.target == "-" or self.target.lower() == "stdout":
                self._fh = sys.stdout
                self._close_fh = False
            else:
                os.makedirs(os.path.dirname(self.target) or ".", exist_ok=True)
                self._fh = open(self.target, "a", buffering=1)
                self._close_fh = True
                
        elif self.mode == "syslog_udp":
            if ":" in str(self.target):
                h, p = str(self.target).rsplit(":", 1)
                self._target_addr = (h, int(p))
            else:
                self._target_addr = ("127.0.0.1", int(self.target))
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
        elif self.mode in ("syslog_tcp", "tcp"):
            if ":" in str(self.target):
                h, p = str(self.target).rsplit(":", 1)
                self._target_addr = (h, int(p))
            else:
                self._target_addr = ("127.0.0.1", int(self.target)) if str(self.target).isdigit() else (str(self.target), 601)
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect(self._target_addr)
            
        elif self.mode == "http":
            self._url = self.target
            if not self._url.startswith(("http://", "https://")):
                self._url = f"http://{self._url}"
                
        elif self.mode in ("journald", "journal"):
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self._sock_path = self.target
    
    def _send(self, line):
        if not line:
            return
        
        if self.mode in ("file", "stdout", "stdio"):
            self._fh.write(line + "\n")
            self._fh.flush()  # Immediate line-by-line flush (no buffering)
            
        elif self.mode == "syslog_udp":
            self._sock.sendto(line.encode("utf-8"), self._target_addr)
            
        elif self.mode in ("syslog_tcp", "tcp"):
            self._sock.sendall(line.encode("utf-8") + b"\n")
            
        elif self.mode == "http":
            is_json = line.strip().startswith(("{", "["))
            content_type = "application/json" if is_json else "text/plain; charset=utf-8"
            req = urllib.request.Request(
                self._url,
                data=line.encode("utf-8"),
                headers={
                    "Content-Type": content_type,
                    "User-Agent": f"ulpf-emulator/{self.identifier}"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    pass
            except Exception:
                pass
                
        elif self.mode in ("journald", "journal"):
            try:
                # Systemd journal native datagram protocol (newline-delimited fields)
                payload = (
                    f"MESSAGE={line}\n"
                    f"SYSLOG_IDENTIFIER={self.identifier}\n"
                    f"PRIORITY=6\n"
                ).encode("utf-8")
                self._sock.sendto(payload, self._sock_path)
            except Exception:
                pass
    
    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self
    
    def _run(self):
        start_time = time.time()
        while not self._stop_event.is_set():
            if self.duration > 0 and (time.time() - start_time) >= self.duration:
                break
            line = self.generator()
            if line:
                self._send(line)
                self.count += 1
            # Real-world inter-arrival time (Poisson process)
            if self.rate > 0:
                time.sleep(random.expovariate(self.rate))
            else:
                time.sleep(0.001)
    
    def stop(self):
        self._stop_event.set()
        self.running = False
        if hasattr(self, "_thread"):
            self._thread.join(timeout=5)
        if hasattr(self, "_fh") and self._close_fh and self._fh:
            self._fh.close()
        if hasattr(self, "_sock") and self._sock:
            self._sock.close()
    
    def __enter__(self):
        return self.start()
    
    def __exit__(self, *args):
        self.stop()


def parse_args(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("-n", "--count", type=int, default=0,
                   help="Batch mode: number of events (0 = real-time stream mode)")
    p.add_argument("-o", "--output", default="-",
                   help="Output target (file path, '-' for stdout, host:port, URL, or journal socket)")
    p.add_argument("--mode", choices=["file", "stdout", "syslog_udp", "syslog_tcp", "http", "tcp", "journald"],
                   default="file", help="Output transport mode")
    p.add_argument("--rate", type=float, default=10,
                   help="Events per second (Poisson process, default: 10)")
    p.add_argument("--duration", type=int, default=0,
                   help="Stream duration in seconds (0 = infinite)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--quiet", action="store_true",
                   help="Suppress status messages to stderr")
    return p.parse_args()
