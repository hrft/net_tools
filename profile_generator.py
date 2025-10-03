#!/usr/bin/env python3
# profile_generator.py
# ساخت .nmconnection قابل نصب برای SSTP (قابل اجرا بدون sudo برای تولید فایل محلی)
import uuid
from datetime import datetime
import argparse
import os
import sys
from textwrap import dedent

TEMPLATE = """[connection]
id={id}
uuid={uuid}
type=vpn
autoconnect=false
timestamp={timestamp}

[vpn]
connection-type=password
gateway={gateway}
password-flags=0
refuse-chap=yes
refuse-pap=yes
require-mschap-v2=yes
user={user}
service-type=org.freedesktop.NetworkManager.sstp

[vpn-secrets]
password={password}

[ipv4]
method=auto

[ipv6]
addr-gen-mode=stable-privacy
method=auto

[proxy]
"""

def generate(profile_prefix, ip, user, password):
    uid = str(uuid.uuid4())
    ts = int(datetime.now().timestamp())
    profile_id = f"{profile_prefix}-{ip.replace('.', '-')}"
    content = TEMPLATE.format(
        id=profile_id,
        uuid=uid,
        timestamp=ts,
        gateway=ip,
        user=user,
        password=password
    )
    filename = f"{profile_id}.nmconnection"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(dedent(content))
    return filename, content

def make_install_script(filename, profile_id):
    script = f"""#!/usr/bin/env bash
set -e
SRC="$(pwd)/{filename}"
DST="/etc/NetworkManager/system-connections/{filename}"
echo "Copying $SRC to $DST"
cp "$SRC" "$DST"
chown root:root "$DST"
chmod 600 "$DST"
echo "Reloading NetworkManager connections"
nmcli connection reload
echo "Ensuring vpn.user-name and vpn.secrets are set for {profile_id}"
nmcli connection modify "{profile_id}" vpn.user-name "{profile_id.split('-',1)[0]}"
nmcli connection modify "{profile_id}" vpn.password-flags 0
nmcli connection modify "{profile_id}" +vpn.secrets "password={args.password}"
nmcli connection modify "{profile_id}" connection.permissions ""
echo "Reloading again"
nmcli connection reload
echo "Bringing up connection {profile_id}"
nmcli connection up "{profile_id}"
"""
    install_name = f"install-{filename}.sh"
    with open(install_name, "w", encoding="utf-8") as s:
        s.write(script)
    os.chmod(install_name, 0o750)
    return install_name

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate .nmconnection for SSTP")
    p.add_argument("ip", help="Gateway IP of VPN server")
    p.add_argument("--prefix", default="vpngate", help="Profile name prefix")
    p.add_argument("--user", default="vpn", help="VPN username")
    p.add_argument("--password", default="vpn", help="VPN password (written into file)")
    p.add_argument("--install-script", action="store_true", help="Also emit a root install script")
    args = p.parse_args()

    filename, content = generate(args.prefix, args.ip, args.user, args.password)
    print(f"Generated: {filename}")
    print("--- content ---")
    print(content)
    if args.install_script:
        # create install script with embedded password; careful: requires sudo to run
        install_name = make_install_script(filename, f"{args.prefix}-{args.ip.replace('.', '-')}")
        print(f"Install script: {install_name}")
        print("Run with sudo to install and activate:")
        print(f"  sudo bash {install_name}")

