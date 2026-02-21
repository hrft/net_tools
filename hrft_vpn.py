import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import socket, ssl, subprocess, threading, os

class HRFT_VPN_FIXED:
    def __init__(self, root):
        self.root = root
        self.root.title("HRFT VPN - Simple & Fast")
        self.root.geometry("800x600")
        self.sudo_password = tk.StringVar()
        
        # --- Sudo Pass ---
        tk.Label(root, text="Sudo Password:").pack(pady=5)
        tk.Entry(root, textvariable=self.sudo_password, show="*", width=30).pack()

        # --- Buttons ---
        frame = tk.Frame(root)
        frame.pack(pady=10)
        tk.Button(frame, text="Load CSV", command=self.load_csv, width=15).grid(row=0, column=0, padx=5)
        self.scan_btn = tk.Button(frame, text="Scan", command=self.start_scan, state="disabled", width=15)
        self.scan_btn.grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Flush Cache", command=self.flush, bg="orange").grid(row=0, column=2, padx=5)

        # --- Table ---
        self.tree = ttk.Treeview(root, columns=("H", "C", "S"), show='headings')
        self.tree.heading("H", text="Server Address")
        self.tree.heading("C", text="Country")
        self.tree.heading("S", text="Speed (MB/s)")
        self.tree.pack(pady=10, fill="both", expand=True)

        # --- Final Buttons ---
        self.conn_btn = tk.Button(root, text="CONNECT", bg="green", fg="white", command=self.connect, state="disabled", height=2, width=20)
        self.conn_btn.pack(pady=10)
        tk.Button(root, text="DISCONNECT", bg="red", fg="white", command=self.stop).pack()

    def load_csv(self):
        self.file = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if self.file: self.scan_btn.config(state="normal")

    def start_scan(self):
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        with open(self.file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.split(",")
                # در فایل vpngate استاندارد: 
                # parts[0] = Hostname, parts[1] = IP, parts[4] = Speed, parts[6] = Country
                if len(parts) > 10 and not line.startswith("*") and "HostName" not in line:
                    host = parts[0]
                    if self.check(host):
                        try:
                            mb = round(float(parts[4]) / 8 / 10**6, 2)
                        except: mb = 0
                        self.tree.insert("", "end", values=(host, parts[6], f"{mb} MB/s"))
        self.conn_btn.config(state="normal")

    def check(self, host):
        try:
            with socket.create_connection((host, 443), timeout=0.5) as s:
                ssl.create_default_context().wrap_socket(s, server_hostname=host)
                return True
        except: return False

    def connect(self):
        sel = self.tree.focus()
        if not sel: return
        host = self.tree.item(sel)['values'][0]
        pw = self.sudo_password.get()
        # دستور مستقیم و ساده شده
        cmd = f"echo '{pw}' | sudo -S sstpc --cert-warn --user vpn --password vpn {host} -- defaultroute usepeerdns lock nodetach"
        threading.Thread(target=lambda: os.system(cmd), daemon=True).start()
        messagebox.showinfo("Status", "Connecting... check your internet in 10 seconds.")

    def flush(self):
        pw = self.sudo_password.get()
        os.system(f"echo '{pw}' | sudo -S ip route flush cache")
        os.system(f"echo '{pw}' | sudo -S pkill sstpc")

    def stop(self):
        self.flush()

if __name__ == "__main__":
    root = tk.Tk(); app = HRFT_VPN_FIXED(root); root.mainloop()