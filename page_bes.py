from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QLabel, QComboBox, QMessageBox, QSpinBox, QDialog, 
                             QDialogButtonBox, QFormLayout, QProgressDialog)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QObject  # NEW: threading helpers for smooth UI.
from database import Database
from user_config import load_config, save_config

class BesTutarDialog(QDialog):
    def __init__(self, ad_soyad, gunluk_tutar, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Beş Tutarı Düzenle - {ad_soyad}")
        self.setFixedSize(300, 150)
        layout = QFormLayout(self)
        
        self.spin_tutar = QSpinBox()
        self.spin_tutar.setRange(1, 1000)
        self.spin_tutar.setValue(int(gunluk_tutar))
        self.spin_tutar.setSuffix(" ₺")
        layout.addRow("Günlük Beş Tutarı:", self.spin_tutar)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_value(self):
        return float(self.spin_tutar.value())

class BesLoadWorker(QObject):
    """BES verilerini arka planda yukler."""
    finished = Signal(list, dict)  # WHY: bes_data, status_map.
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
            bes_data = self.db.get_bes_hesaplama_list(self.year, self.month, tersane_id=self.tersane_id)
            status_map = self.db.get_bes_personel_status_map()
            self.finished.emit(bes_data, status_map)  # WHY: return data for UI update.
        except Exception as e:
            self.error.emit(str(e))

class BesCalcWorker(QObject):
    """BES hesaplamasini arka planda calistirir."""
    finished = Signal(list)  # WHY: results list from calculate_bes_for_month.
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
            results = self.db.calculate_bes_for_month(self.year, self.month, tersane_id=self.tersane_id)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class BesYonetimiPage(QWidget):
    def __init__(self, signal_manager):
        super().__init__()
        self.db = Database()
        self.signal_manager = signal_manager
        self.tersane_id = 0  # NEW: active tersane id for BES scoping.
        self._needs_refresh = False  # NEW: lazy-load flag to avoid heavy refresh on hidden tabs.
        self._load_thread = None  # NEW: keep thread reference to avoid premature GC.
        self._load_worker = None  # NEW: keep worker reference to avoid GC while thread runs.
        self._calc_thread = None  # NEW: keep BES calc thread reference.
        self._calc_worker = None  # NEW: keep BES calc worker reference.
        self._calc_dialog = None  # NEW: progress dialog during BES calculation.
        self.setup_ui()
        cfg = load_config()
        today = datetime.now()
        year = cfg.get("bes_year", today.year)
        month = cfg.get("bes_month", today.month)
        try:
            year = int(year)
        except Exception:
            year = today.year
        try:
            month = int(month)
        except Exception:
            month = today.month
        if month < 1 or month > 12:
            month = today.month
        self.combo_month.blockSignals(True)
        self.spin_year.blockSignals(True)
        self.combo_month.setCurrentIndex(month - 1)
        self.spin_year.setValue(year)
        self.combo_month.blockSignals(False)
        self.spin_year.blockSignals(False)
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
        
        # Başlık
        title = QLabel("💰 BES (Bireysel Emeklilik Sistemi) Yönetimi")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Filtre
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Ay:"))
        self.combo_month = QComboBox()
        self.combo_month.addItems(["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                                   "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"])
        today = datetime.now()
        self.combo_month.setCurrentIndex(today.month - 1)
        self.combo_month.currentIndexChanged.connect(self._on_period_changed)
        filter_layout.addWidget(self.combo_month)
        
        filter_layout.addWidget(QLabel("Yıl:"))
        self.spin_year = QSpinBox()
        self.spin_year.setRange(2020, 2030)
        self.spin_year.setValue(today.year)
        self.spin_year.valueChanged.connect(self._on_period_changed)
        filter_layout.addWidget(self.spin_year)
        layout.addLayout(filter_layout)
        
        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Personel", "Çalışılan Gün", "Günlük Tutar", "Aylık BES", "Devam Ediyor", "İşlemler"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        hint_lbl = QLabel("Ipuclari: Sutun basligina tikla sirala")
        hint_lbl.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint_lbl)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_hesapla = QPushButton("🔄 Beş Hesapla")
        btn_hesapla.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        btn_hesapla.clicked.connect(self.calculate_bes)
        btn_layout.addWidget(btn_hesapla)
        
        btn_personel_ekle = QPushButton("👤 Beş Listesine Ekle")
        btn_personel_ekle.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        btn_personel_ekle.clicked.connect(self.add_personel)
        btn_layout.addWidget(btn_personel_ekle)
        
        layout.addLayout(btn_layout)
        layout.addStretch()

    def _on_period_changed(self):
        cfg = load_config()
        cfg["bes_year"] = int(self.spin_year.value())
        cfg["bes_month"] = self.combo_month.currentIndex() + 1
        save_config(cfg)
        self.load_data()

    def load_data(self):
        self._start_load_worker()  # WHY: load BES data in background to keep UI responsive.

    def _start_load_worker(self):
        """Arka planda BES verisini yukler (UI donmasini engeller)."""
        if self._load_thread and self._load_thread.isRunning():
            return  # WHY: do not start a second load while one is running.
        year = self.spin_year.value()
        month = self.combo_month.currentIndex() + 1
        self._load_thread = QThread()  # WHY: run DB work off the UI thread.
        worker = BesLoadWorker(self.db, year, month, self.tersane_id)
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

    def _on_load_finished(self, bes_data, status_map):
        """BES listesini tabloya uygular."""
        try:
            sorting = self.table.isSortingEnabled()
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)
            for ad_soyad, calisilan_gun, gunluk_tutar, aylik_bes in bes_data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(ad_soyad))
                self.table.setItem(row, 1, QTableWidgetItem(str(calisilan_gun)))
                self.table.setItem(row, 2, QTableWidgetItem(f"{gunluk_tutar:.2f} ₺"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{aylik_bes:.2f} ₺"))
                devam_ediyor = status_map.get(ad_soyad, 0)
                if devam_ediyor == 1:
                    btn_durum = QPushButton("✓ Devam Ediyor")
                    btn_durum.setStyleSheet("background-color: #4CAF50; color: white;")
                else:
                    btn_durum = QPushButton("✗ Devam Etmiyor")
                    btn_durum.setStyleSheet("background-color: #E53935; color: white;")
                btn_durum.clicked.connect(lambda checked, ad=ad_soyad: self.toggle_bes_status(ad))
                self.table.setCellWidget(row, 4, btn_durum)
                btn_edit = QPushButton("✏️ Düzenle")
                btn_edit.setStyleSheet("background-color: #FF9800; color: white;")
                btn_edit.clicked.connect(lambda checked, ad=ad_soyad, gt=gunluk_tutar: self.edit_tutar(ad, gt))
                self.table.setCellWidget(row, 5, btn_edit)
            self.table.setSortingEnabled(sorting)
        except RuntimeError:
            try:
                self.table.setSortingEnabled(True)
            except Exception:
                pass
            pass  # SAFEGUARD: UI object may be gone; ignore late signals.

    def _on_load_error(self, msg):
        """Arka plan BES hatasi."""
        QMessageBox.critical(self, "Hata", f"BES yuklenemedi: {msg}")

    def _on_load_thread_finished(self):
        """Thread kapaninca referanslari temizle."""
        self._load_thread = None  # WHY: clear thread ref after it has fully stopped.
        self._load_worker = None  # WHY: clear worker ref after thread completion.

    def calculate_bes(self):
        self._start_calc_worker()
        return
        year = self.spin_year.value()
        month = self.combo_month.currentIndex() + 1
        
        try:
            results = self.db.calculate_bes_for_month(year, month, tersane_id=self.tersane_id)  # WHY: scope BES calculation to active tersane.
            if results:
                toplam = sum(r['aylik_bes'] for r in results)
                QMessageBox.information(self, "Başarılı", 
                    f"Beş hesaplandı!\n\n{len(results)} personel için\nToplam: {toplam:.2f} ₺")
                self.load_data()
            else:
                QMessageBox.information(self, "Bilgi", "Hesaplanacak beş listesi boş.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beş hesaplanırken hata: {e}")

    def _start_calc_worker(self):
        """BES hesaplamasini arka planda calistir (UI donmasini engeller)."""
        if self._calc_thread and self._calc_thread.isRunning():
            return  # WHY: do not start a second calc while one is running.
        year = self.spin_year.value()
        month = self.combo_month.currentIndex() + 1

        # Progress dialog (indeterminate)
        self._calc_dialog = QProgressDialog("BES hesaplanÄ±yor...", None, 0, 0, self)
        self._calc_dialog.setWindowModality(Qt.WindowModal)  # WHY: keep user focused during long calc.
        self._calc_dialog.setAutoClose(False)  # WHY: close explicitly on finish/error.
        self._calc_dialog.setAutoReset(False)
        self._calc_dialog.setMinimumDuration(0)
        self._calc_dialog.show()

        self._calc_thread = QThread()  # WHY: run heavy work off the UI thread.
        worker = BesCalcWorker(self.db, year, month, self.tersane_id)
        self._calc_worker = worker  # WHY: keep a strong reference to avoid GC while running.
        worker.moveToThread(self._calc_thread)  # WHY: execute worker in background thread.
        self._calc_thread.started.connect(worker.run)  # WHY: start work when thread starts.
        worker.finished.connect(self._on_calc_finished)  # WHY: update UI when data is ready.
        worker.error.connect(self._on_calc_error)  # WHY: show errors without crashing UI.
        worker.finished.connect(self._calc_thread.quit)  # WHY: stop thread event loop after completion.
        worker.finished.connect(worker.deleteLater)  # WHY: free worker object safely in Qt.
        worker.error.connect(self._calc_thread.quit)  # WHY: stop thread on error to avoid orphan threads.
        worker.error.connect(worker.deleteLater)  # WHY: free worker on error path.
        self._calc_thread.finished.connect(self._on_calc_thread_finished)  # WHY: clear refs only after thread stops.
        self._calc_thread.finished.connect(self._calc_thread.deleteLater)  # WHY: free thread object after finish.
        self._calc_thread.start()  # WHY: start background work now that signals are wired.

    def _on_calc_finished(self, results):
        """BES hesaplamasi tamamlandi."""
        if self._calc_dialog:
            try:
                self._calc_dialog.close()
            except RuntimeError:
                pass
        self._calc_dialog = None
        if results:
            toplam = sum(r['aylik_bes'] for r in results)
            QMessageBox.information(self, "BaÅŸarÄ±lÄ±",
                f"BeÅŸ hesaplandÄ±!\n\n{len(results)} personel iÃ§in\nToplam: {toplam:.2f} â‚º")
            self.load_data()
        else:
            QMessageBox.information(self, "Bilgi", "Hesaplanacak beÅŸ listesi boÅŸ.")

    def _on_calc_error(self, msg):
        """BES hesaplama hatasi."""
        if self._calc_dialog:
            try:
                self._calc_dialog.close()
            except RuntimeError:
                pass
        self._calc_dialog = None
        QMessageBox.critical(self, "Hata", f"BeÅŸ hesaplanÄ±rken hata: {msg}")

    def _on_calc_thread_finished(self):
        """Calc thread kapaninca referanslari temizle."""
        self._calc_thread = None
        self._calc_worker = None

    def toggle_bes_status(self, ad_soyad):
        # Durum döğüşmek için dialog aç
        try:
            status_map = self.db.get_bes_personel_status_map()
            current_status = status_map.get(ad_soyad, 0)
            new_status = 0 if current_status == 1 else 1
            self.db.set_bes_personel_status(ad_soyad, new_status)

            if new_status == 0:
                # İptal seçilen aydan sonraki dönemlerde geçerli olsun
                year = self.spin_year.value()
                month = self.combo_month.currentIndex() + 1
                next_year, next_month = year, month + 1
                if next_month == 13:
                    next_month = 1
                    next_year += 1
                self.db.delete_bes_hesaplama_from(ad_soyad, next_year, next_month)
                QMessageBox.information(
                    self, "Bilgi",
                    f"{ad_soyad}'nın beşi iptal edildi. {next_year}-{next_month:02d} itibarıyla kesinti durur."
                )
            else:
                QMessageBox.information(self, "Bilgi", f"{ad_soyad}'nın beşi aktif hale getirildi.")
            
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"İşlem başarısız: {e}")

    def edit_tutar(self, ad_soyad, gunluk_tutar):
        dlg = BesTutarDialog(ad_soyad, gunluk_tutar, self)
        if dlg.exec() == QDialog.Accepted:
            yeni_tutar = dlg.get_value()
            self.db.add_bes_personel(ad_soyad, yeni_tutar)
            QMessageBox.information(self, "Başarılı", f"{ad_soyad}'nın günlük beş tutarı {yeni_tutar} ₺ olarak güncellendi.")
            self.load_data()

    def add_personel(self):
        # Tüm personelleri getir ve beş listesine ekle
        year = self.spin_year.value()
        month = self.combo_month.currentIndex() + 1
        all_personel = self.db.get_personnel_names_for_tersane(self.tersane_id, year, month)  # WHY: keep list in sync with active tersane.
        if not all_personel:
            QMessageBox.warning(self, "Hata", "Personel listesi boş.")
            return
        
        # Seçim dialogu
        from PySide6.QtWidgets import QInputDialog
        personel, ok = QInputDialog.getItem(self, "Personel Seç", 
                                            "Beş listesine eklenecek personeli seçin:", 
                                            all_personel, 0, False)
        if ok and personel:
            gunluk_fiyat = float(self.db.get_setting('gunluk_bes_fiyati', 20.0))
            self.db.add_bes_personel(personel, gunluk_fiyat)
            QMessageBox.information(self, "Başarılı", f"{personel} beş listesine eklendi.")
            self.load_data()
