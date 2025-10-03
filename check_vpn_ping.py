#!/usr/bin/env python3
"""
check_vpn_ping.py
خواندن vpngate.net.csv، پینگ محلی برای هر IP انجام دادن،
فیلتر کردن سرورهای پاسخگو، و نوشتن good_vpn.csv با فرمت خواسته‌شده.

مثال اجرا:
python3 check_vpn_ping.py -i vpngate.net.csv -o good_vpn.csv --timeout 2 --workers 20
"""

import argparse
import pandas as pd
import subprocess
import re
import concurrent.futures
import math
from pathlib import Path

def ping_ip(ip: str, timeout: int = 2) -> (bool, float):
    """
    پینگ یکبار به ip بفرست و میانگین/زمان پاسخ را برگردان.
    برمی‌گرداند: (reachable: bool, ping_ms: float or None)
    """
    try:
        # linux: -c 1 (یک بسته)، -W timeout (ثانیه برای انتظار پاسخ)
        proc = subprocess.run(["ping", "-c", "1", "-W", str(timeout), ip],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL,
                              text=True)
        if proc.returncode != 0:
            return False, None
        out = proc.stdout

        # سعی کن اول مقدار time=... ms را پیدا کنی
        m = re.search(r"time[=<]?\s*([\d\.]+)\s*ms", out)
        if m:
            return True, float(m.group(1))

        # fallback به خط rtt min/avg/max/mdev = ...
        m2 = re.search(r"=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)\s*ms", out)
        if m2:
            avg = float(m2.group(2))
            return True, avg

        # اگر چیزی پیدا نشد ولی returncode==0 فرض کن reachable اما ping نداشتیم
        return True, None
    except FileNotFoundError:
        raise RuntimeError("فرمان `ping` روی سیستم پیدا نشد. بررسی کن که iputils-ping نصب باشه.")
    except Exception:
        return False, None

def convert_speed_to_mbps(speed_val, units):
    """
    تبدیل مقدار سرعت به Mbps بر اساس units:
    units in {'bps','Bps','kbps','mbps'}
    """
    try:
        v = float(speed_val)
    except Exception:
        return math.nan

    if units == "bps":
        return v / 1_000_000.0
    if units == "Bps":
        # Bytes per second -> convert to megabits: Bps * 8 / 1e6
        return (v * 8) / 1_000_000.0
    if units == "kbps":
        return v / 1_000.0
    if units == "mbps":
        return v
    return math.nan

def convert_traffic_to_gb(traffic_val, units):
    """
    تبدیل ترافیک به گیگابایت (GB). units in {'bytes','KB','MB','GB'}
    """
    try:
        v = float(traffic_val)
    except Exception:
        return math.nan

    if units == "bytes":
        return v / (1024**3)  # تبدیل بایت -> GiB (نمایش به عنوان GB)
    if units == "KB":
        return v / (1024**2)
    if units == "MB":
        return v / 1024.0
    if units == "GB":
        return v
    return math.nan

def main():
    p = argparse.ArgumentParser(description="Filter vpngate CSV by local ping and produce good_vpn.csv")
    p.add_argument("-i", "--input", default="vpngate.net.csv", help="ورودی CSV از vpngate (پیش‌فرض vpngate.net.csv)")
    p.add_argument("-o", "--output", default="good_vpn.csv", help="فایل خروجی (پیش‌فرض good_vpn.csv)")
    p.add_argument("-t", "--timeout", type=int, default=2, help="timeout برای هر ping (ثانیه)")
    p.add_argument("-w", "--workers", type=int, default=20, help="تعداد thread برای پینگ همزمان")
    p.add_argument("--speed-units", choices=["bps","Bps","kbps","mbps"], default="bps",
                   help="واحد ستون Speed در CSV (پیش‌فرض bps = بیت/ثانیه)")
    p.add_argument("--traffic-units", choices=["bytes","KB","MB","GB"], default="bytes",
                   help="واحد ستون TotalTraffic (پیش‌فرض bytes)")
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"فایل ورودی پیدا نشد: {input_path}")
        return

    # خواندن CSV (اگر جداکننده ; داشت تلاش می‌کنیم)
    try:
        df = pd.read_csv(input_path)
    except Exception:
        df = pd.read_csv(input_path, sep=";")

    # ستون‌های مورد نیاز
    cols_needed = ["IP","Score","Ping","Speed","CountryLong","NumVpnSessions","Uptime","TotalUsers","TotalTraffic"]
    # بعضی ستون‌ها ممکنه وجود نداشته باشن — بررسی کن
    missing = [c for c in cols_needed if c not in df.columns]
    if missing:
        print("هشدار: ستون(های) زیر در فایل ورودی پیدا نشدند:", missing)
    # انتخاب ستون‌هایی که موجود هستند (با ترتیب موردنظر برای نگهداری اولیه)
    present = [c for c in cols_needed if c in df.columns]
    df_sel = df[present].copy()

    # تابعی برای ping هر IP (قابل استفاده با threadpool)
    ips = df_sel['IP'].astype(str).tolist()

    results = {}
    print(f"شروع پینگِ {len(ips)} آدرس با timeout={args.timeout}s ...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        future_to_ip = {ex.submit(ping_ip, ip, args.timeout): ip for ip in ips}
        processed = 0
        for fut in concurrent.futures.as_completed(future_to_ip):
            ip = future_to_ip[fut]
            processed += 1
            try:
                reachable, ping_ms = fut.result()
            except Exception as e:
                reachable, ping_ms = False, None
            results[ip] = (reachable, ping_ms)
            if processed % 20 == 0 or processed == len(ips):
                print(f"... پردازش شد {processed}/{len(ips)}")

    # افزودن نتایج پینگ به df_sel
    df_sel['__reachable__'] = df_sel['IP'].map(lambda ip: results.get(str(ip), (False, None))[0])
    df_sel['__ping_ms__'] = df_sel['IP'].map(lambda ip: results.get(str(ip), (False, None))[1])

    # فقط نگه دار سرورهایی که reachable هستند
    df_good = df_sel[df_sel['__reachable__'] == True].copy()
    print(f"پاسخ‌گو: {len(df_good)} از {len(df_sel)}")

    if df_good.empty:
        print("هیچ سروری از این موقعیت پاسخ نداد.")
        # فایل خروجی را به صورت خالی با هدر مورد نظر بساز
        columns_out = ["IP","Score","Ping: ms","Speed: Mbps","CountryLong",
                       "NumVpnSessions","Uptime","TotalUsers","TotalTraffic: GB"]
        pd.DataFrame(columns=columns_out).to_csv(args.output, index=False)
        print(f"فایل خروجی خالی ساخته شد: {args.output}")
        return

    # تبدیل Speed -> Mbps و TotalTraffic -> GB
    df_good['Speed: Mbps'] = df_good['Speed'].apply(lambda v: convert_speed_to_mbps(v, args.speed_units) if 'Speed' in df_good.columns else math.nan)
    df_good['TotalTraffic: GB'] = df_good['TotalTraffic'].apply(lambda v: convert_traffic_to_gb(v, args.traffic_units) if 'TotalTraffic' in df_good.columns else math.nan)

    # ستون Ping: ms از مقدار اندازه‌گیری شده
    df_good['Ping: ms'] = df_good['__ping_ms__']

    # آماده‌سازی نهایی: انتخاب و تغییر نام ستون‌ها طبق خواسته‌ی تو
    out_cols_order = [
        "IP",
        "Score",
        "Ping: ms",
        "Speed: Mbps",
        "CountryLong",
        "NumVpnSessions",
        "Uptime",
        "TotalUsers",
        "TotalTraffic: GB"
    ]
    # اگر بعضی ستون‌ها در df_good موجود نبودند، آنها را با NaN اضافه کن
    for c in out_cols_order:
        if c not in df_good.columns:
            df_good[c] = math.nan

    df_out = df_good[out_cols_order].copy()

    # فرمت نمایش: گرد کردن اعداد
    df_out['Ping: ms'] = pd.to_numeric(df_out['Ping: ms'], errors='coerce').round(2)
    df_out['Speed: Mbps'] = pd.to_numeric(df_out['Speed: Mbps'], errors='coerce').round(2)
    df_out['TotalTraffic: GB'] = pd.to_numeric(df_out['TotalTraffic: GB'], errors='coerce').round(2)

    # مرتب‌سازی: ابتدا ping صعودی، سپس سرعت نزولی
    df_out = df_out.sort_values(by=["Ping: ms", "Speed: Mbps"], ascending=[True, False])

    # ذخیره
    df_out.to_csv(args.output, index=False)
    print(f"خروجی ذخیره شد: {args.output}  ({len(df_out)} رکورد)")

if __name__ == "__main__":
    main()
