from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton, QMessageBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from server_loader import fetch_servers_from_csv
from vpn_manager import VPNManager
from utils import test_ip, ping_test

CSV_PATH = "vpngate_list.csv"

class VPNLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🛡️ لانچر SSTP (ماژولار)")
        self.setGeometry(100, 100, 1000, 600)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFont(QFont("Vazirmatn", 8))

        self.vpn = VPNManager()
        self.servers = fetch_servers_from_csv(CSV_PATH)
        self.filtered = self.servers.copy()

        self.init_ui()

        self.ping_timer = QTimer(self)
        self.ping_timer.setInterval(5000)
        self.ping_timer.timeout.connect(self.live_ping)

    def init_ui(self):
        main = QVBoxLayout()

        # جدول
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["IP", "HostName", "Ping", "Speed"])
        self.populate_table(self.filtered)
        main.addWidget(self.table)

        # دکمه‌ها
        btns = QHBoxLayout()
        self.btn_connect = QPushButton("اتصال")
        self.btn_connect.clicked.connect(self.connect_vpn)
        self.btn_disconnect = QPushButton("قطع")
        self.btn_disconnect.clicked.connect(self.disconnect_vpn)
        self.btn_test_ip = QPushButton("تست IP بیرونی")
        self.btn_test_ip.clicked.connect(self.show_ip)
        btns.addWidget(self.btn_connect)
        btns.addWidget(self.btn_disconnect)
        btns.addWidget(self.btn_test_ip)
        main.addLayout(btns)

        # وضعیت
        self.status = QLabel("وضعیت: ❌ متصل نیست")
        main.addWidget(self.status)

        self.ping_label = QLabel("پینگ زنده: -")
        main.addWidget(self.ping_label)

        self.setLayout(main)

    def populate_table(self, data):
        self.table.setRowCount(len(data))
        for i, s in enumerate(data):
            values = [s["IP"], s["HostName"], s["Ping"], f'{s["SpeedMb"]:.2f}']
            for j, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()

    def connect_vpn(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "انتخاب نشده", "یک سرور انتخاب کنید")
            return
        ip = self.filtered[row]["IP"]
        out = self.vpn.connect(ip)
        self.status.setText(out)
        self.ping_timer.start()

    def disconnect_vpn(self):
        out = self.vpn.disconnect()
        self.status.setText(out)
        self.ping_timer.stop()
        self.ping_label.setText("پینگ زنده: -")

    def show_ip(self):
        ip = test_ip()
        if ip:
            QMessageBox.information(self, "IP بیرونی", f"🌍 {ip}")
        else:
            QMessageBox.warning(self, "خطا", "عدم دسترسی به اینترنت")

    def live_ping(self):
        t = ping_test()
        if t:
            self.ping_label.setText(f"پینگ زنده: {t}")
        else:
            self.ping_label.setText("پینگ زنده: شکست")

