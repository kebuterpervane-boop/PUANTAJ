from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QLabel, QComboBox, QMessageBox, QSpinBox,
                             QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QDateEdit)
from PySide6.QtCore import Qt, QDate
from database import Database

class DisiplinEkleDialog(QDialog):
    def __init__(self, personel_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Disiplin/Ödül Kaydı Ekle")
        self.setFixedSize(400, 250)
        layout = QFormLayout(self)
        
        self.combo_personel = QComboBox()
        self.combo_personel.addItems(personel_list)
        layout.addRow("Personel:", self.combo_personel)
        
        self.combo_tur = QComboBox()
        self.combo_tur.addItems(["İyileştirme Notu", "Yazılı Uyarı", "Disiplin Cezası", 
                                 "Başarı Ödülü", "Verimlilik Bonusu", "Diğer"])
        layout.addRow("Tür:", self.combo_tur)
        
        self.date_kayit = QDateEdit()
        self.date_kayit.setCalendarPopup(True)
        self.date_kayit.setDate(QDate.currentDate())
        layout.addRow("Tarih:", self.date_kayit)
        
        self.spin_tutar = QSpinBox()
        self.spin_tutar.setRange(-10000, 10000)
        self.spin_tutar.setValue(0)
        self.spin_tutar.setSuffix(" ₺")
        layout.addRow("Tutar (Ödül +/Ceza -):", self.spin_tutar)
        
        self.input_aciklama = QLineEdit()
        layout.addRow("Açıklama:", self.input_aciklama)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_values(self):
        return {
            'personel': self.combo_personel.currentText(),
            'tur': self.combo_tur.currentText(),
            'tarih': self.date_kayit.date().toPython().strftime('%Y-%m-%d'),
            'tutar': float(self.spin_tutar.value()),
            'aciklama': self.input_aciklama.text()
        }

class DisiplinYonetimiPage(QWidget):
    def __init__(self, signal_manager):
        super().__init__()
        self.db = Database()
        self.signal_manager = signal_manager
        self.setup_ui()
        self.load_data()
        self.signal_manager.data_updated.connect(self.load_data)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Başlık
        title = QLabel("⚖️ Disiplin/Ödül Yönetimi")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Filtre
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Personel:"))
        self.combo_personel_filter = QComboBox()
        self.combo_personel_filter.addItem("Tümü")
        all_personel = [p[0] for p in self.db.get_all_personnel_detailed()]
        self.combo_personel_filter.addItems(all_personel)
        self.combo_personel_filter.currentTextChanged.connect(self.load_data)
        filter_layout.addWidget(self.combo_personel_filter)
        
        filter_layout.addWidget(QLabel("Tür:"))
        self.combo_tur_filter = QComboBox()
        self.combo_tur_filter.addItems(["Tümü", "İyileştirme Notu", "Yazılı Uyarı", "Disiplin Cezası",
                                         "Başarı Ödülü", "Verimlilik Bonusu"])
        self.combo_tur_filter.currentTextChanged.connect(self.load_data)
        filter_layout.addWidget(self.combo_tur_filter)
        
        layout.addLayout(filter_layout)
        
        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Personel", "Tür", "Tarih", "Tutar", "Açıklama", "İşlemler"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ekle = QPushButton("➕ Kayıt Ekle")
        btn_ekle.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        btn_ekle.clicked.connect(self.add_kayit)
        btn_layout.addWidget(btn_ekle)
        
        layout.addLayout(btn_layout)
        layout.addStretch()

    def load_data(self):
        self.table.setRowCount(0)
        
        # Basit statik demo veri (gerçekte database'ten gelecek)
        demo_data = [
            ("AHMET ASLANBURUT", "İyileştirme Notu", "2025-12-01", 0, "Düzenli gelişim gösterüyor"),
            ("ASİF İNCE", "Verimlilik Bonusu", "2025-12-15", 500, "Ay içinde proje tamamlandı"),
            ("ALİ GÜLMAN", "Disiplin Cezası", "2025-12-10", -250, "İş güvenliği ihlali"),
        ]
        
        for ad, tur, tarih, tutar, aciklama in demo_data:
            if self.combo_personel_filter.currentText() != "Tümü":
                if ad != self.combo_personel_filter.currentText():
                    continue
            
            if self.combo_tur_filter.currentText() != "Tümü":
                if tur != self.combo_tur_filter.currentText():
                    continue
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(ad))
            self.table.setItem(row, 1, QTableWidgetItem(tur))
            self.table.setItem(row, 2, QTableWidgetItem(tarih))
            
            tutar_text = f"+{tutar} ₺" if tutar > 0 else f"{tutar} ₺"
            tutar_item = QTableWidgetItem(tutar_text)
            if tutar > 0:
                tutar_item.setForeground(Qt.green)
            elif tutar < 0:
                tutar_item.setForeground(Qt.red)
            self.table.setItem(row, 3, tutar_item)
            
            self.table.setItem(row, 4, QTableWidgetItem(aciklama))
            
            btn_sil = QPushButton("🗑️ Sil")
            btn_sil.setStyleSheet("background-color: #f44336; color: white;")
            self.table.setCellWidget(row, 5, btn_sil)

    def add_kayit(self):
        all_personel = [p[0] for p in self.db.get_all_personnel_detailed()]
        if not all_personel:
            QMessageBox.warning(self, "Hata", "Personel listesi boş.")
            return
        
        dlg = DisiplinEkleDialog(all_personel, self)
        if dlg.exec() == QDialog.Accepted:
            vals = dlg.get_values()
            # Burada database kaydı yapılacak
            QMessageBox.information(self, "Başarılı", f"{vals['personel']} için {vals['tur']} kaydı eklendi.")
            self.load_data()
