#!/usr/bin/env python3
import csv
import socket
import ssl
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

INPUT = Path("vpngate.net.csv")
OUTPUT = Path("vpn_good.csv")
MAX_WORKERS = 30 

def speed_to_mbps(raw_speed):
    try:
        return round(float(raw_speed.replace(",", "")) / 1000000.0, 2)
    except:
        return 0.0

def check_sstp_protocol(target, port=443, timeout=3.0):
    """بررسی واقعی قابلیت اتصال SSTP از طریق SSL Handshake"""
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with socket.create_connection((target, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=target) as ssock:
                return True
    except Exception:
        return False

def test_single(row):
    # دریافت Hostname و تشخیص پورت (اگر ذکر شده باشد)
    full_host = row.get("HostName") or row.get("IP")
    if not full_host: return None
    
    if ":" in full_host:
        host, port = full_host.split(":")
        port = int(port)
    else:
        host = full_host
        port = 443 # پورت پیش‌فرض

    if check_sstp_protocol(host, port):
        return {
            "Hostname": host,
            "IP": row["IP"],
            "Port": port,
            "SpeedMb": speed_to_mbps(row.get("Speed", "0")),
            "Country": row["CountryLong"],
            "Protocol": "SSTP"
        }
    return None

def connect_to_vpn(server):
    """اجرای فرمان اتصال SSTP در اوبونتو با ساختار صحیح پارامترها"""
    print(f"\n[!] تلاش برای اتصال خودکار به سریع‌ترین سرور: {server['Hostname']} در {server['Country']}")
    
    # ساختار جدید: sstpc [options] hostname -- [pppd-options]
    # یوزر و پسورد vpngate همیشه vpn است
    cmd = [
        "sudo", "sstpc", 
        "--cert-warn", 
        "--user", "vpn", 
        "--password", "vpn", 
        f"{server['Hostname']}:{server['Port']}",
        "--",               # جداکننده پارامترهای pppd
        "noauth",           # پارامترهای pppd از اینجا به بعد
        "nodefaultroute",   # جلوگیری از تداخل اگر کانکشن دیگری دارید
        "usepeerdns",       # استفاده از DNS سرور VPN
        "refuse-eap",
        "refuse-chap",
        "refuse-mschap"
    ]
    
    try:
        # استفاده از Popen برای نمایش لحظه‌ای لاگ‌های اتصال
        process = subprocess.Popen(cmd)
        print(f"\n[+] در حال برقراری اتصال... (برای قطع کردن Ctrl+C بزنید)")
        process.wait()
    except KeyboardInterrupt:
        print("\n[!] درخواست قطع اتصال دریافت شد.")
        subprocess.run(["sudo", "pkill", "sstpc"])

def main():
    if not INPUT.exists():
        print(f"فایل ورودی یافت نشد: {INPUT}")
        return

    with open(INPUT, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # --- رفع باگ خط اول (و پنهان‌تر: خط هدر) ---
    # فایل CSV دانلودی از VPN Gate دو خط متادیتای غیر-CSV داره که
    # csv.DictReader به‌تنهایی نمی‌تونه درستش کنه:
    #   خط ۱ -> *vpn_servers        (و معمولاً یک خط "*" مشابه هم در انتهای فایل)
    #   خط ۲ -> #HostName,IP,...    (این هدر واقعیه، ولی با یک # اضافه جلوش)
    # به‌جای حذف دستیِ خط اول، اینجا هر خطی که با * شروع بشه به‌صورت خودکار
    # فیلتر میشه و # ابتدای خط هدر هم برداشته میشه، بنابراین دیگر نیازی به
    # ویرایش دستی فایل ورودی قبل از اجرا نیست.
    lines = [ln for ln in lines if not ln.startswith("*")]
    if lines and lines[0].startswith("#"):
        lines[0] = lines[0][1:]

    reader = csv.DictReader(lines)
    unique_servers = {r["IP"]: r for r in reader if r.get("IP")}.values()

    print(f"در حال بررسی {len(unique_servers)} سرور...")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(test_single, r) for r in unique_servers]
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                results.append(res)
                print(f"[OK] {res['Hostname']}:{res['Port']} ({res['Country']})")

    results.sort(key=lambda x: x["SpeedMb"], reverse=True)
    
    # ذخیره در فایل خروجی با ستون Port
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Hostname", "IP", "Port", "SpeedMb", "Country", "Protocol"])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\nپایان اسکن. {len(results)} مورد یافت شد.")

    # اتصال به اولین مورد در صورت وجود نتیجه
    if results:
        connect_to_vpn(results[0])
    else:
        print("هیچ سرور فعالی پیدا نشد.")

if __name__ == "__main__":
    main()
