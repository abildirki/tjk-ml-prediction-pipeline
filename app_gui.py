import sys
import os
import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QComboBox, QPushButton, QLabel, 
                               QTextEdit, QMessageBox, QGroupBox)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QIcon

# Handle Path for Dev vs Frozen
if getattr(sys, 'frozen', False):
    # If frozen (EXE), we are running inside strict boundaries. 
    # PyInstaller puts modules in sys.path automatically.
    pass 
else:
    # If dev (python app_gui.py), we need src in path
    sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    from tjk.coupon_generator import CouponGenerator
except ImportError as e:
    # Fallback/Debug for when running in confused environments
    # Trying to find where we are
    raise ImportError(f"Could not import 'tjk.coupon_generator'. Path: {sys.path}. Error: {e}")

class Worker(QThread):
    finished = Signal(dict)
    
    def __init__(self, city):
        super().__init__()
        self.city = city
        
    def run(self):
        gen = CouponGenerator()
        # Always use today's date
        today = datetime.date.today()
        try:
            result = gen.process(self.city, today)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"error": str(e)})

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TJK Yapay Zeka Kupon Oluşturucu")
        self.setGeometry(100, 100, 600, 800)
        
        self.setup_ui()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header = QLabel("🏇 TJK Tahmin v2")
        header.setAlignment(Qt.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Bold))
        main_layout.addWidget(header)
        
        # Controls
        control_layout = QHBoxLayout()
        
        self.city_combo = QComboBox()
        self.city_combo.addItems(["Adana", "İstanbul", "İzmir", "Bursa", "Ankara", "Kocaeli", "Antalya", "Diyarbakır", "Şanlıurfa", "Elazığ"])
        control_layout.addWidget(QLabel("Şehir:"))
        control_layout.addWidget(self.city_combo)
        
        self.btn_generate = QPushButton("🎲 Bugünün Kuponunu Üret")
        self.btn_generate.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_generate.clicked.connect(self.start_generation)
        control_layout.addWidget(self.btn_generate)
        
        main_layout.addLayout(control_layout)
        
        # Output Area
        self.out_group = QGroupBox("Tahmin Sonuçları")
        out_layout = QVBoxLayout()
        
        # Banko & Risk
        info_layout = QHBoxLayout()
        self.lbl_banko = QLabel("Banko: -")
        self.lbl_banko.setStyleSheet("color: blue; font-weight: bold;")
        self.lbl_risk = QLabel("Riskli Ayaklar: -")
        self.lbl_risk.setStyleSheet("color: red;")
        info_layout.addWidget(self.lbl_banko)
        info_layout.addWidget(self.lbl_risk)
        out_layout.addLayout(info_layout)
        
        # Eco Coupon
        out_layout.addWidget(QLabel("🎫 Ekonomik Kupon:"))
        self.txt_eco = QTextEdit()
        self.txt_eco.setReadOnly(True)
        self.txt_eco.setMaximumHeight(150)
        out_layout.addWidget(self.txt_eco)
        
        # Wide Coupon
        out_layout.addWidget(QLabel("🛡️ Geniş Kupon:"))
        self.txt_wide = QTextEdit()
        self.txt_wide.setReadOnly(True)
        out_layout.addWidget(self.txt_wide)
        
        self.out_group.setLayout(out_layout)
        main_layout.addWidget(self.out_group)
        
        # Telegram Button
        self.btn_telegram = QPushButton("✈️ Telegram'a Gönder")
        self.btn_telegram.setStyleSheet("background-color: #0088cc; color: white; font-weight: bold; padding: 10px;")
        self.btn_telegram.clicked.connect(self.send_telegram)
        self.btn_telegram.setEnabled(False) # Disabled until generated
        main_layout.addWidget(self.btn_telegram)
        
        # Status Bar
        self.statusBar().showMessage("Hazır")
        
    def start_generation(self):
        city = self.city_combo.currentText()
        self.btn_generate.setEnabled(False)
        self.statusBar().showMessage(f"{city} için veriler çekiliyor ve analiz ediliyor... Lütfen bekleyin.")
        self.txt_eco.clear()
        self.txt_wide.clear()
        
        self.worker = Worker(city)
        self.worker.finished.connect(self.handle_result)
        self.worker.start()
        
    def handle_result(self, result):
        self.btn_generate.setEnabled(True)
        
        if "error" in result:
            QMessageBox.critical(self, "Hata", result["error"])
            self.statusBar().showMessage("Hata oluştu.")
            return
            
        self.statusBar().showMessage("Tahmin başarıyla üretildi.")
        
        self.lbl_banko.setText(f"Banko: {result['banko']}")
        self.lbl_risk.setText(f"Riskli: {result['risky']}")
        
        self.txt_eco.setText(result['eco'])
        self.txt_wide.setText(result['wide'])
        
        self.last_result = result
        self.btn_telegram.setEnabled(True)
        
    def send_telegram(self):
        # Mock Telegram Sending for now as no token provided
        # In real scenario, we would request token or read from config
        QMessageBox.information(self, "Telegram", "Telegram mesajı gönderildi! \n(Simülasyon - Token yapılandırılmalı)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
