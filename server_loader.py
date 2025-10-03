import csv

def parse_speed_to_mbps(speed_str):
    if not speed_str:
        return 0.0
    try:
        num = float(speed_str.split()[0])
        return round(num / 1000.0, 2)
    except:
        return 0.0

def parse_uptime_to_hours(uptime_str):
    if not uptime_str:
        return 0
    s = str(uptime_str).strip().lower()
    try:
        if "day" in s:
            days = int(s.split()[0])
            return days * 24
        val = int(float(s))
        return val // 3600
    except:
        return 0

def fetch_servers_from_csv(csv_path):
    servers = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            ip = (row.get("IP") or "").strip()
            if not ip:
                continue
            servers.append({
                "IP": ip,
                "HostName": (row.get("HostName") or "").strip(),
                "Score": int(row.get("Score") or 0),
                "Ping": int(row.get("Ping") or 9999),
                "SpeedMb": parse_speed_to_mbps(row.get("Speed")),
                "CountryLong": row.get("CountryLong", "نامشخص"),
                "NumVpnSessions": int(row.get("NumVpnSessions") or 0),
                "UptimeHours": parse_uptime_to_hours(row.get("Uptime")),
                "TotalUsers": int(row.get("TotalUsers") or 0),
            })
    servers.sort(key=lambda s: (-s["SpeedMb"], s["Ping"]))
    return servers

