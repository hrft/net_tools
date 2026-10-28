import customtkinter as ctk
import csv, socket, ssl, subprocess, threading
from tkinter import filedialog

class HRFT_VPN_PRO(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HRFT VPN - Ultimate Edition")
        self.geometry("900x600")
        self.selected_server = None
        self.vpn_process = None

        # UI Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(self.sidebar, text="HRFT VPN", font=("Arial", 20, "bold")).pack(pady=20)
        
        self.btn_load = ctk.CTkButton(self.sidebar, text="۱. انتخاب فایل CSV", command=self.load_csv)
        self.btn_load.pack(pady=10, padx=10)
        
        self.btn_scan = ctk.CTkButton(self.sidebar, text="۲. اسکن پایداری", command=self.start_scan, state="disabled")
        self.btn_scan.pack(pady=10, padx=10)

        # Server List (Main Area)
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="لیست سرورهای SSTP (یکی را انتخاب کنید)")
        self.scroll_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.server_buttons = []

        # Footer Status
        self.status_bar = ctk.CTkFrame(self, height=50)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        self.lbl_status = ctk.CTkLabel(self.status_bar, text="وضعیت: آماده")
        self.lbl_status.pack(side="left", padx=20)

        self.btn_connect = ctk.CTkButton(self.status_bar, text="اتصال کل سیستم", fg_color="green", command=self.connect, state="disabled")
        self.btn_connect.pack(side="right", padx=10)
        
        self.btn_stop = ctk.CTkButton(self.status_bar, text="قطع اتصال", fg_color="red", command=self.stop)
        self.btn_stop.pack(side="right", padx=10)

    def load_csv(self):
        path = filedialog.askopenfilename()
        if path:
            self.csv_path = path
            self.btn_scan.configure(state="normal")
            self.lbl_status.configure(text="فایل آماده اسکن است.")

    def start_scan(self):
        for btn in self.server_buttons: btn.destroy()
        self.server_buttons = []
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        self.lbl_status.configure(text="در حال اسکن پروتکل SSL...")
        with open(self.csv_path, "r") as f:
            servers = list(csv.DictReader(f))
        
        valid_count = 0
        for s in servers:
            host = s.get("Hostname") or s.get("IP")
            if self.check_ssl(host):
                valid_count += 1
                self.add_server_to_list(s, host)
        self.lbl_status.configure(text=f"اسکن تمام شد. {valid_count} سرور یافت شد.")

    def check_ssl(self, host):
        try:
            with socket.create_connection((host, 443), timeout=1.5) as sock:
                ssl.create_default_context().wrap_socket(sock, server_hostname=host)
                return True
        except: return False

    def add_server_to_list(self, data, host):
        info = f"{data.get('CountryLong', 'Unknown')} | Speed: {data.get('Speed', '0')} bps"
        btn = ctk.CTkRadioButton(self.scroll_frame, text=info, command=lambda: self.select(host))
        btn.pack(fill="x", padx=10, pady=5)
        self.server_buttons.append(btn)

    def select(self, host):
        self.selected_server = host
        self.btn_connect.configure(state="normal")
        self.lbl_status.configure(text=f"انتخاب شد: {host}")

    def connect(self):
        cmd = [
            "sudo", "sstpc", "--cert-warn", "--user", "vpn", "--password", "vpn", 
            self.selected_server, "--", "defaultroute", "usepeerdns", "lock"
        ]
        self.lbl_status.configure(text="در حال اتصال... (کل سیستم)")
        threading.Thread(target=lambda: subprocess.run(cmd), daemon=True).start()
        self.btn_connect.configure(state="disabled")

    def stop(self):
        subprocess.run(["sudo", "pkill", "sstpc"])
        self.lbl_status.configure(text="اتصال قطع شد.")
        self.btn_connect.configure(state="normal")

if __name__ == "__main__":
    app = HRFT_VPN_PRO()
    app.mainloop()