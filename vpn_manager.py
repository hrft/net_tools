# vpn_manager.py
import subprocess

class VPNManager:
    def __init__(self):
        self.current_profile = None

    def run_cmd(self, cmd, use_sudo=True):
        full = ["sudo"] + cmd if use_sudo else cmd
        try:
            out = subprocess.check_output(full, stderr=subprocess.STDOUT, text=True)
            return out.strip()
        except subprocess.CalledProcessError as e:
            return e.output.strip()

    def delete_profile(self, profile_name):
        existing = self.run_cmd(["nmcli", "-t", "-f", "NAME", "connection", "show"])
        if profile_name in existing:
            self.run_cmd(["nmcli", "connection", "delete", profile_name])

    def connect(self, ip):
        profile_name = f"vpngate-{ip.replace('.', '-')}"
        self.current_profile = profile_name

        # پاک کردن پروفایل ناقص قبلی
        self.delete_profile(profile_name)

        # 1) ساخت پروفایل پایه
        add_out = self.run_cmd([
            "nmcli", "connection", "add",
            "type", "vpn",
            "con-name", profile_name,
            "ifname", "*",
            "vpn-type", "sstp"
        ])

        # 2) ست کردن داده‌های SSTP
        modify_data_out = self.run_cmd([
            "nmcli", "connection", "modify", profile_name,
            "vpn.service-type", "org.freedesktop.NetworkManager.sstp",
            "vpn.connection-type", "password",
            "vpn.gateway", ip,
            "vpn.user-name", "vpn",          # 🔥 این خط اضافه شد
            "vpn.refuse-chap", "yes",
            "vpn.refuse-pap", "yes",
            "vpn.require-mschap-v2", "yes",
            "vpn.password-flags", "0"
        ])

        # 3) اضافه کردن پسورد
        modify_secrets_out = self.run_cmd([
            "nmcli", "connection", "modify", profile_name,
            "vpn.secrets", "password=vpn"
        ])

        # 4) دسترسی برای همه‌ی یوزرها
        perms_out = self.run_cmd([
            "nmcli", "connection", "modify", profile_name,
            "connection.permissions", ""
        ])

        # 5) reload
        self.run_cmd(["nmcli", "connection", "reload"])

        # 6) نمایش کانفیگ نهایی
        show_out = self.run_cmd(["nmcli", "connection", "show", profile_name], use_sudo=False)

        # 7) اتصال
        up_out = self.run_cmd(["nmcli", "connection", "up", profile_name])

        # برگرداندن لاگ کامل برای UI
        result = (
            f"ADD:\n{add_out}\n\n"
            f"DATA:\n{modify_data_out}\n\n"
            f"SECRETS:\n{modify_secrets_out}\n\n"
            f"PERMS:\n{perms_out}\n\n"
            f"SHOW:\n{show_out}\n\n"
            f"UP:\n{up_out}"
        )
        return result

    def disconnect(self):
        if self.current_profile:
            return self.run_cmd(["nmcli", "connection", "down", self.current_profile])
        return "❌ هیچ پروفایلی متصل نیست"

