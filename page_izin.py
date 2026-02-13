from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QLabel, QComboBox, QMessageBox, QDateEdit, QSpinBox,
                             QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QCheckBox,
                             QTabWidget, QGroupBox)
from PySide6.QtCore import Qt, QDate, QThread, Signal, Slot, QObject  # NEW: threading helpers for smooth UI.
from database import Database

class IzinEkleDialog(QDialog):
    def __init__(self, personel_list, izin_turleri=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İzin Kaydı Ekle")
        self.setFixedSize(400, 280)
        layout = QFormLayout(self)
        
        self.combo_personel = QComboBox()
        self.combo_personel.addItems(personel_list)
        layout.addRow("Personel:", self.combo_personel)
        
        self.date_baslangic = QDateEdit()
        self.date_baslangic.setCalendarPopup(True)
        self.date_baslangic.setDate(QDate.currentDate())
        layout.addRow("Başlangıç Tarihi:", self.date_baslangic)

        self.date_bitis = QDateEdit()
        self.date_bitis.setCalendarPopup(True)
        self.date_bitis.setDate(QDate.currentDate())
        layout.addRow("Bitiş Tarihi:", self.date_bitis)
        
        self.combo_tur = QComboBox()
        izin_turleri = list(izin_turleri or [])
        if not izin_turleri:
            izin_turleri = ["Hasta", "Raporlu", "Özür", "Yıllık İzin", "Doğum İzni", "İdari İzin", "Diğer"]
        self.combo_tur.addItems(izin_turleri)
        layout.addRow("İzin Türü:", self.combo_tur)
        
        self.spin_gun = QSpinBox()
        self.spin_gun.setRange(1, 365)
        self.spin_gun.setValue(1)
        self.spin_gun.setReadOnly(True)
        layout.addRow("Gün Sayısı:", self.spin_gun)
        
        self.input_aciklama = QLineEdit()
        layout.addRow("Açıklama:", self.input_aciklama)
        
        self.date_baslangic.dateChanged.connect(self.update_gun_sayisi)
        self.date_bitis.dateChanged.connect(self.update_gun_sayisi)
        self.update_gun_sayisi()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_values(self):
        return {
            'personel': self.combo_personel.currentText(),
            'tarih': self.date_baslangic.date().toPython().strftime('%Y-%m-%d'),
            'tur': self.combo_tur.currentText(),
            'gun': int(self.spin_gun.value()),
            'aciklama': self.input_aciklama.text()
        }

    def update_gun_sayisi(self):
        bas = self.date_baslangic.date()
        bit = self.date_bitis.date()
        if bit < bas:
            bit = bas
            self.date_bitis.setDate(bas)
        
        # Pazarları çıkararak hesapla (yıllık izinden düşmesin)
        gun_sayisi = 0
        current = bas
        while current <= bit:
            # Pazar değilse say (Qt'de Pazar = 7)
            if current.dayOfWeek() != 7:
                gun_sayisi += 1
            current = current.addDays(1)
        
        self.spin_gun.setValue(max(1, gun_sayisi))

class IzinLoadWorker(QObject):
    """Izin listesini arka planda yukler."""
    finished = Signal(list)  # WHY: send izin_list back to UI thread.
    error = Signal(str)  # WHY: surface errors without blocking UI thread.

    def __init__(self, db, year, month, tersane_id=0):
        super().__init__()
        self.db = db  # WHY: keep DB access same as before, only off UI thread.
        self.year = year
        self.month = month
        self.tersane_id = tersane_id or 0  # WHY: normalize to keep behavior consistent with global (0) mode.

    @Slot()
    def run(self):
        try:
            izin_list = self.db.get_izin_list(self.year, self.month, tersane_id=self.tersane_id)
            self.finished.emit(izin_list)  # WHY: return data for UI update.
        except Exception as e:
            self.error.emit(str(e))

class IzinYonetimiPage(QWidget):
    def __init__(self, signal_manager):
        super().__init__()
        self.db = Database()
        self.signal_manager = signal_manager
        self.tersane_id = 0  # NEW: active tersane id for leave scoping.
        self._needs_refresh = False  # NEW: lazy-load flag to avoid heavy refresh on hidden tabs.
        self._load_thread = None  # NEW: keep thread reference to avoid premature GC.
        self._load_worker = None  # NEW: keep worker reference to avoid GC while thread runs.
        self.setup_ui()
        self.load_data()
        self.signal_manager.data_updated.connect(self._on_data_updated)  # NEW: lazy refresh to avoid hidden-tab work.

    def set_tersane_id(self, tersane_id, refresh=True):
        """Global tersane seçiciden gelen tersane_id'yi set eder ve verileri yeniler."""
        self.tersane_id = tersane_id
        self._needs_refresh = True  # WHY: mark dirty; refresh can be deferred.
        if refresh:
            self.update_view()  # WHY: only visible page refreshes to keep UI smooth.

    def update_view(self):
        """Görünür sayfa için güncel tersane verilerini yükle."""
        self._needs_refresh = False  # WHY: clear dirty flag after refresh.
        self.load_data()

    def refresh_if_needed(self):
        """Lazy-load için: sayfa görünür olduğunda gerekiyorsa güncelle."""
        if self._needs_refresh:
            self.update_view()

    def _on_data_updated(self):
        """Veri değiştiğinde sadece görünürsek yenile (lazy)."""
        if not self.isVisible():
            self._needs_refresh = True  # WHY: defer heavy refresh until tab is visible.
            return
        self.update_view()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab widget
        tabs = QTabWidget()
        
        # İzin Kaydı Tab
        izin_widget = QWidget()
        izin_layout = QVBoxLayout(izin_widget)
        
        # Başlık
        title = QLabel("📋 İzin Yönetimi")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        izin_layout.addWidget(title)
        
        # Filtre
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Ay:"))
        self.combo_month = QComboBox()
        self.combo_month.addItems(["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                                   "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"])
        today = datetime.now()
        self.combo_month.setCurrentIndex(today.month - 1)
        self.combo_month.currentIndexChanged.connect(self.load_data)
        filter_layout.addWidget(self.combo_month)
        
        filter_layout.addWidget(QLabel("Yıl:"))
        self.combo_year = QComboBox()
        self.combo_year.addItems([str(y) for y in range(2024, 2030)])
        self.combo_year.setCurrentText(str(today.year))
        self.combo_year.currentTextChanged.connect(self.load_data)
        filter_layout.addWidget(self.combo_year)
        izin_layout.addLayout(filter_layout)
        
        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Personel", "Tarih", "Tür", "Gün", "Durum", "İşlemler"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        izin_layout.addWidget(self.table)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ekle = QPushButton("➕ İzin Ekle")
        btn_ekle.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        btn_ekle.clicked.connect(self.add_izin)
        btn_layout.addWidget(btn_ekle)
        
        izin_layout.addLayout(btn_layout)
        izin_layout.addStretch()
        
        tabs.addTab(izin_widget, "İzin Kaydı")
        
        # İzin Ayarları Tab
        ayarlar_widget = QWidget()
        ayarlar_layout = QVBoxLayout(ayarlar_widget)
        
        ayarlar_title = QLabel("⚙️ İzin Türü Ayarları")
        ayarlar_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        ayarlar_layout.addWidget(ayarlar_title)
        
        info_label = QLabel("Yevmiye verilecek izin türlerini seçin:")
        ayarlar_layout.addWidget(info_label)
        
        # Checkbox grubu
        self.checkbox_dict = {}
        izin_ayarlari = self.db.get_izin_ayarlari()
        
        group = QGroupBox("İzin Türleri")
        group_layout = QVBoxLayout(group)
        
        for tur, otomatik in izin_ayarlari:
            checkbox = QCheckBox(f"{tur}")
            checkbox.setChecked(bool(otomatik))
            checkbox.stateChanged.connect(lambda state, t=tur: self.save_izin_ayari(t))
            self.checkbox_dict[tur] = checkbox
            group_layout.addWidget(checkbox)
        
        ayarlar_layout.addWidget(group)
        ayarlar_layout.addStretch()
        
        tabs.addTab(ayarlar_widget, "İzin Ayarları")
        
        layout.addWidget(tabs)

    def save_izin_ayari(self, izin_turu):
        """İzin türü ayarını kaydet"""
        checkbox = self.checkbox_dict[izin_turu]
        self.db.set_izin_otomatik_kayit(izin_turu, checkbox.isChecked())

    def load_data(self):
        self._start_load_worker()  # WHY: load izin data in background to keep UI responsive.

    def _start_load_worker(self):
        """Arka planda izin verisini yukler (UI donmasini engeller)."""
        if self._load_thread and self._load_thread.isRunning():
            return  # WHY: do not start a second load while one is running.
        year = int(self.combo_year.currentText())
        month = self.combo_month.currentIndex() + 1
        self._load_thread = QThread()  # WHY: run DB work off the UI thread.
        worker = IzinLoadWorker(self.db, year, month, self.tersane_id)
        self._load_worker = worker  # WHY: keep a strong reference to avoid GC while running.
        worker.moveToThread(self._load_thread)  # WHY: execute worker in background thread.
        self._load_thread.started.connect(worker.run)  # WHY: start work when thread starts.
        worker.finished.connect(self._on_load_finished)  # WHY: update UI when data is ready.
        worker.error.connect(self._on_load_error)  # WHY: show errors without crashing UI.
        worker.finished.connect(self._load_thread.quit)  # WHY: stop thread event loop after completion.
        worker.finished.connect(worker.deleteLater)  # WHY: free worker object safely in Qt.
        worker.error.connect(self._load_thread.quit)  # WHY: stop thread on error to avoid orphan threads.
        worker.error.connect(worker.deleteLater)  # WHY: free worker on error path.
        self._load_thread.finished.connect(self._on_load_thread_finished)  # WHY: clear references only after thread stops.
        self._load_thread.finished.connect(self._load_thread.deleteLater)  # WHY: free thread object after finish.
        self._load_thread.start()  # WHY: start background work now that signals are wired.

    def _on_load_finished(self, izin_list):
        """Izin listesini tabloya uygular."""
        try:
            self.table.setRowCount(0)
            for row_data in izin_list:
                izin_id, ad_soyad, tarih, tur, gun, aciklama, onay = row_data
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(ad_soyad))
                self.table.setItem(row, 1, QTableWidgetItem(tarih))
                self.table.setItem(row, 2, QTableWidgetItem(tur))
                self.table.setItem(row, 3, QTableWidgetItem(str(gun)))
                durum_text = "✓ Onaylı" if onay else "⏳ Bekleme"
                durum_item = QTableWidgetItem(durum_text)
                self.table.setItem(row, 4, durum_item)
                btn_sil = QPushButton("🗑️ Sil")
                btn_sil.setStyleSheet("background-color: #f44336; color: white;")
                btn_sil.clicked.connect(lambda checked, izin_id=izin_id: self.delete_izin(izin_id))
                self.table.setCellWidget(row, 5, btn_sil)
        except RuntimeError:
            pass  # SAFEGUARD: UI object may be gone; ignore late signals.

    def _on_load_error(self, msg):
        """Arka plan izin hatasi."""
        QMessageBox.critical(self, "Hata", f"Izin yuklenemedi: {msg}")

    def _on_load_thread_finished(self):
        """Thread kapaninca referanslari temizle."""
        self._load_thread = None  # WHY: clear thread ref after it has fully stopped.
        self._load_worker = None  # WHY: clear worker ref after thread completion.

    def add_izin(self):
        year = int(self.combo_year.currentText())
        month = self.combo_month.currentIndex() + 1
        personel_list = self.db.get_personnel_names_for_tersane(self.tersane_id, year, month)  # WHY: keep personel list in sync with active tersane.
        if not personel_list:
            QMessageBox.warning(self, "Hata", "Personel listesi boş.")
            return
        
        izin_turleri = [tur for tur, _ in self.db.get_izin_ayarlari()]
        dlg = IzinEkleDialog(personel_list, izin_turleri, self)
        if dlg.exec() == QDialog.Accepted:
            vals = dlg.get_values()
            try:
                # add_izin_with_auto_kayit kullan - otomatik kayıt yapılacaksa yapılır
                self.db.add_izin_with_auto_kayit(vals['personel'], vals['tarih'], vals['tur'], vals['gun'], vals['aciklama'])
                QMessageBox.information(self, "Başarılı", f"{vals['personel']} için {vals['gun']} gün {vals['tur']} izni eklendi.")
                self.load_data()
                self.signal_manager.data_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"İzin eklenirken hata: {e}")

    def delete_izin(self, izin_id):
        reply = QMessageBox.question(self, "Onay", "Seçili izin kaydı silinecek. Emin misiniz?", 
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_izin(izin_id)
                self.load_data()
                self.signal_manager.data_updated.emit()
                QMessageBox.information(self, "Başarılı", "İzin kaydı silindi.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"İzin silinirken hata: {e}")
