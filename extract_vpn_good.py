#!/usr/bin/env python3
# extract_vpn_good_ping_ports.py
# خواندن vpngate_list.csv، پینگ (ابتدا به IP، سپس پینگ به 1.1.1.1)، بررسی پورت‌های TCP/UDP و تولید vpn_good.csv

import csv
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, List

INPUT = Path("vpngate.net.csv")
OUTPUT = Path("vpn_good.csv")
MAX_WORKERS = 40  # تعدیل کن در صورت نیاز
TCP_PORTS_TO_CHECK = [443, 1194, 80, 53]
UDP_PORTS_TO_CHECK = [1194, 53]  # UDP معمولاً برای OpenVPN/L2TP/DNS و ...؛ قابل تغییر

def parse_number(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    s = s.replace(",", "")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except:
        return None

def speed_to_mbps(raw_speed):
    val = parse_number(raw_speed)
    if val is None:
        return 0.0
    return round(val / 1000.0, 2)

def is_valid_ipv4(ip: str) -> bool:
    try:
        socket.inet_aton(ip)
        return True
    except:
        return False

def resolve_if_needed(host: str) -> Optional[str]:
    if is_valid_ipv4(host):
        return host
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None

def ping_target(target_ip: str, timeout_sec: int = 3) -> Optional[float]:
    """Ping a target (Linux ping). Return RTT in ms or None."""
    try:
        proc = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_sec), target_ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec + 2
        )
        out = proc.stdout + proc.stderr
        if proc.returncode != 0:
            return None
        m = re.search(r"time[=<]\s*([\d\.]+)\s*ms", out)
        if not m:
            m = re.search(r"time=([\d\.]+)", out)
        if m:
            return float(m.group(1))
        return None
    except Exception:
        return None

def check_tcp_port(ip: str, port: int, timeout: float = 2.0) -> bool:
    """Try to connect TCP; return True if connection succeeds."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def check_udp_port(ip: str, port: int, timeout: float = 2.0) -> bool:
    """
    Best-effort UDP check:
    - send a small packet and wait for response (not reliable for many UDP services).
    - If recvfrom returns something, assume open. If ICMP Port Unreachable is returned,
      the socket may get an error or no response; we'll treat no response as unknown/closed.
    Note: This method is not as reliable as TCP check.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        # send a small payload; for DNS we could send a real query but keep generic
        try:
            s.sendto(b"\x00\x00\x00\x00", (ip, port))
        except Exception:
            s.close()
            return False
        try:
            data, _ = s.recvfrom(512)
            s.close()
            return True
        except socket.timeout:
            s.close()
            return False
        except Exception:
            s.close()
            return False
    except Exception:
        return False

def load_rows(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ip = (r.get("IP") or r.get("ip") or r.get("Ip") or "").strip()
            if not ip:
                continue
            country = (r.get("CountryLong") or r.get("Country") or r.get("country") or "").strip()
            speed_raw = r.get("SpeedMb") or r.get("Speed") or r.get("speed") or r.get("Bandwidth") or ""
            rows.append({"IP": ip, "SpeedRaw": speed_raw, "CountryLong": country})
    return rows

def test_single(row):
    """Test a single row:
       1) resolve IP if needed
       2) ping the server IP (quick) -- only proceed if server responds
       3) ping 1.1.1.1 and record RTT (ms)
       4) check TCP/UDP ports and collect open ones
    """
    ip_or_host = row["IP"]
    ip = resolve_if_needed(ip_or_host)
    if not ip:
        return None
    # 1) ping the server itself to see if reachable
    server_ping = ping_target(ip, timeout_sec=2)
    if server_ping is None:
        return None  # skip unreachable server

    # 2) ping 1.1.1.1 (external) for PingTime column
    ping_to_1_1_1_1 = ping_target("1.1.1.1", timeout_sec=3)
    if ping_to_1_1_1_1 is None:
        # if cannot ping 1.1.1.1, still keep server but mark PingTime empty
        ping_to_1_1_1_1_val = ""
    else:
        ping_to_1_1_1_1_val = round(ping_to_1_1_1_1, 2)

    # 3) port checks (concurrent small checks)
    open_ports: List[str] = []
    for p in TCP_PORTS_TO_CHECK:
        try:
            if check_tcp_port(ip, p, timeout=1.5):
                open_ports.append(f"TCP:{p}")
        except Exception:
            pass
    for p in UDP_PORTS_TO_CHECK:
        try:
            if check_udp_port(ip, p, timeout=1.5):
                open_ports.append(f"UDP:{p}")
        except Exception:
            pass

    speed_mb = speed_to_mbps(row["SpeedRaw"])
    return {
        "IP": ip,
        "SpeedMb": speed_mb,
        "CountryLong": row["CountryLong"],
        "PingTime": ping_to_1_1_1_1_val,
        "OpenPort": ";".join(open_ports) if open_ports else ""
    }

def main():
    if not INPUT.exists():
        print(f"Input file not found: {INPUT}")
        return

    rows = load_rows(INPUT)
    # deduplicate preserving first
    seen = set()
    unique = []
    for r in rows:
        if r["IP"] in seen:
            continue
        seen.add(r["IP"])
        unique.append(r)

    results = []
    workers = min(MAX_WORKERS, max(2, len(unique)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(test_single, r): r for r in unique}
        for fut in as_completed(futures):
            try:
                res = fut.result()
            except Exception:
                res = None
            if res:
                results.append(res)

    # sort by SpeedMb desc, then PingTime asc (empty PingTime goes last)
    results.sort(key=lambda x: (-x["SpeedMb"], x["PingTime"] if x["PingTime"] != "" else float("inf")))

    # write csv
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["IP", "SpeedMb", "CountryLong", "PingTime", "OpenPort"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"Wrote {len(results)} rows to {OUTPUT}")

if __name__ == "__main__":
    main()

