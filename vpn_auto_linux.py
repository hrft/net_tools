#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vpn_auto_linux.py
اسکنر و اتو-کانکت SSTP برای لینوکس
فیلتر سرورهای قابل دسترسی از ایران با پینگ،
اتصال خودکار به سریع‌ترین سرور با قابلیت fallback
"""

import csv
import socket
import ssl
import subprocess
import sys
import signal
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ==================== تنظیمات ====================
INPUT_FILE = Path("www.vpngate.net.csv")
RESULT_FILE = Path("vpn_good.csv")
MAX_WORKERS = 40          # تعداد تردهای همزمان برای تست
PING_TIMEOUT = 3          # ثانیه برای تایم‌اوت پینگ
SSL_TIMEOUT = 3           # ثانیه برای تایم‌اوت SSL handshake
CONNECT_TEST_SEC = 12     # ثانیه برای بررسی برقراری اتصال sstpc
CREDENTIALS = ("vpn", "vpn")
# ================================================


def signal_handler(sig, frame):
    print("\n[!] قطع شد توسط کاربر. خروج...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)


def speed_to_mbps(raw_speed):
    try:
        return round(float(str(raw_speed).replace(",", "")) / 1_000_000.0, 2)
    except (ValueError, TypeError):
        return 0.0


def ping_host(ip, timeout=PING_TIMEOUT):
    """
    تست پینگ واقعی با دستور سیستمی.
    خروجی: (ok, latency_ms)
    """
    if not ip:
        return False, 9999.0
    cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout + 2
        )
        if result.returncode != 0:
            return False, 9999.0
        out = result.stdout
        if "time=" in out:
            try:
                time_str = out.split("time=")[1].split()[0]
                return True, float(time_str.replace("ms", ""))
            except (IndexError, ValueError):
                return True, 999.0
        return True, 999.0
    except Exception:
        return False, 9999.0


def check_sstp_ssl(ip, port=443, timeout=SSL_TIMEOUT):
    """بررسی باز بودن پورت ۴۴۳ و قبول SSL"""
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=ip):
                return True
    except Exception:
        return False


def load_servers(filepath):
    """خواندن CSV به صورت بهینه (بدون لود فیلد بیس۶۴ حجیم)"""
    filepath = Path(filepath)
    if not filepath.exists():
        return None
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return []
        
        try:
            idx_ip = header.index("IP")
            idx_host = header.index("HostName")
            idx_speed = header.index("Speed")
            idx_country = header.index("CountryLong")
            idx_score = header.index("Score")
        except ValueError as e:
            print(f"[خطا] ستون مورد نیاز در CSV یافت نشد: {e}")
            sys.exit(1)
        
        unique = {}
        for row in reader:
            if len(row) <= idx_ip:
                continue
            ip = row[idx_ip].strip()
            if ip and ip not in unique:
                unique[ip] = {
                    "IP": ip,
                    "HostName": row[idx_host] if len(row) > idx_host else ip,
                    "Speed": row[idx_speed] if len(row) > idx_speed else "0",
                    "CountryLong": row[idx_country] if len(row) > idx_country else "Unknown",
                    "Score": row[idx_score] if len(row) > idx_score else "0",
                }
        return list(unique.values())


def test_server(row):
    """تست یک سرور: پینگ + SSL"""
    ip = row["IP"]
    ok, latency = ping_host(ip)
    if not ok:
        return None
    if not check_sstp_ssl(ip):
        return None
    return {
        "IP": ip,
        "HostName": row["HostName"],
        "Port": 443,
        "PingMs": round(latency, 1),
        "SpeedMb": speed_to_mbps(row["Speed"]),
        "Country": row["CountryLong"],
        "Score": row["Score"],
    }


def save_results(servers):
    with open(RESULT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["HostName", "IP", "Port", "PingMs", "SpeedMb", "Country", "Score"]
        )
        writer.writeheader()
        writer.writerows(servers)
    print(f"[+] لیست سرورهای سالم در {RESULT_FILE} ذخیره شد.")


def get_connect_command(server):
    """ساخت دستور sstpc با/بدون sudo"""
    user, passwd = CREDENTIALS
    base = [
        "sstpc",
        "--cert-warn",
        "--user", user,
        "--password", passwd,
        f"{server['IP']}:{server['Port']}",
        "--",
        "noauth",
        "nodefaultroute",
        "usepeerdns",
        "refuse-eap",
        "refuse-chap",
        "refuse-mschap"
    ]
    if os.geteuid() != 0:
        return ["sudo"] + base
    return base


def try_connect(server):
    """
    تلاش برای اتصال. اگر sstpc بعد از CONNECT_TEST_SEC هنوز زنده بود،
    یعنی اتصال برقرار شده.
    """
    cmd = get_connect_command(server)
    print(f"    اجرا: {' '.join(cmd[:6])} ...")
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        try:
            stdout, _ = proc.communicate(timeout=CONNECT_TEST_SEC)
            err = stdout.strip()[-400:] if stdout.strip() else "Unknown error"
            print(f"    [خطا] sstpc زود بسته شد: {err}")
            return False
            
        except subprocess.TimeoutExpired:
            print(f"\n[✓] موفق! متصل شدی به {server['IP']} ({server['Country']})")
            print(f"    پینگ: {server['PingMs']} میلی‌ثانیه | سرعت: {server['SpeedMb']} مگابیت")
            print(f"\n[!] برای قطع اتصال Ctrl+C بزنید.\n")
            
            try:
                proc.wait()
            except KeyboardInterrupt:
                print("\n[!] در حال قطع اتصال...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print("[+] اتصال قطع شد.")
            return True
            
    except FileNotFoundError:
        print("    [خطا] دستور sstpc یافت نشد. نصب کنید: sudo apt install sstp-client")
        return False
    except Exception as e:
        print(f"    [خطا] {e}")
        return False


def connect_with_fallback(servers):
    total = len(servers)
    for idx, srv in enumerate(servers, 1):
        print(f"\n[*] [{idx}/{total}] تلاش برای اتصال به {srv['IP']} ({srv['Country']})")
        print(f"    پینگ: {srv['PingMs']}ms | سرعت: {srv['SpeedMb']} Mbps")
        
        if try_connect(srv):
            return True
        print("    [-] ناموفق. سرور بعدی...")
    
    print("\n[!] هیچ‌کدام از سرورها متصل نشدند.")
    return False


def main():
    print("=" * 60)
    print("VPN Gate SSTP Auto-Connector — نسخه لینوکس")
    print("=" * 60)
    
    if not shutil.which("sstpc"):
        print("[!] هشدار: sstpc نصب نیست. ابتدا اجرا کنید:")
        print("    sudo apt update && sudo apt install sstp-client\n")
    
    servers = load_servers(INPUT_FILE)
    if servers is None:
        print(f"[خطا] فایل {INPUT_FILE} یافت نشد.")
        sys.exit(1)
    
    print(f"[1] {len(servers)} سرور یکتا لود شد. شروع تست از موقعیت ایران...")
    
    working = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(test_server, s): s for s in servers}
        for future in as_completed(futures):
            res = future.result()
            if res:
                working.append(res)
                print(f"    [OK] {res['IP']} | پینگ:{res['PingMs']}ms | "
                      f"سرعت:{res['SpeedMb']}Mbps | {res['Country']}")
    
    if not working:
        print("\n[!] هیچ سرور SSTP قابل دسترسی از ایران یافت نشد.")
        sys.exit(1)
    
    working.sort(key=lambda x: (x["PingMs"], -x["SpeedMb"]))
    
    print(f"\n[2] {len(working)} سرور سالم پیدا شد. ۵ تای برتر:")
    for i, s in enumerate(working[:5], 1):
        print(f"    #{i} {s['IP']} ({s['Country']}) | "
              f"پینگ:{s['PingMs']}ms | سرعت:{s['SpeedMb']}Mbps")
    
    save_results(working)
    
    print("\n[3] شروع اتصال خودکار با fallback...")
    connect_with_fallback(working)


if __name__ == "__main__":
    main()
