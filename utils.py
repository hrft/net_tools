import subprocess
import requests

def test_ip():
    try:
        return requests.get("https://checkip.amazonaws.com", timeout=5).text.strip()
    except:
        return None

def ping_test():
    try:
        out = subprocess.check_output(["ping", "-c", "1", "-W", "2", "1.1.1.1"], text=True)
        if "time=" in out:
            return [p for p in out.split() if p.startswith("time=")][0].split("=")[1]
        return None
    except:
        return None

