import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget,
                             QMessageBox, QFrame, QLineEdit, QDialog, QSizePolicy, QComboBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from user_config import load_config, save_config
from signals import SignalManager
from database import Database
from page_upload import UploadPage
from page_records import RecordsPage
from page_personnel import PersonnelPage
from page_avans import AvansPage
from page_dashboard import DashboardPage
from page_holidays import HolidaysPage
from page_payslip import PayslipPage
from page_settings import SettingsPage
from page_bes import BesYonetimiPage
from page_izin import IzinYonetimiPage
from page_raporlar import RaporlarPage
from version import __version__, __app_name__
from update_check import check_for_update

class LoginDialog(QDialog):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Giriş - Saral Puantaj")
        self.setFixedSize(300, 200)
        layout = QVBoxLayout(self)
        self.user = QLineEdit(placeholderText="Kullanıcı Adı")
        self.pwd = QLineEdit(placeholderText="Şifre")
        self.pwd.setEchoMode(QLineEdit.Password)
        btn = QPushButton("Giriş Yap")
        btn.clicked.connect(self.check)
        layout.addWidget(QLabel("🚢 TERSANE PUANTAJ"))
        layout.addWidget(self.user)
        layout.addWidget(self.pwd)
        layout.addWidget(btn)

    def check(self):
        # Güvenlik: Veritabanından kontrol
        if self.db.check_login(self.user.text(), self.pwd.text()):
            self.accept()
        else:
            QMessageBox.warning(self, "Hata", "Giriş başarısız")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Saral Group - Tersane Puantaj v{__version__}")
        self.setMinimumSize(1400, 850)
        self.resize(1400, 900)

        # --- İzin Ayarlarını Başlat ---
        self.db = Database()
        self.db.init_izin_ayarlari()

        # --- Güncelleme kontrolü ---
        self.check_updates()

        self.signal_manager = SignalManager()

        # Aktif tersane ID - başlangıçta ilk tersane
        tersaneler = self.db.get_tersaneler()
        self.aktif_tersane_id = tersaneler[0][0] if tersaneler else None

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ═══════════════════════════════════════════
        # GLOBAL TERSANE SEÇİCİ ÜST BAR
        # ═══════════════════════════════════════════
        top_bar = QFrame()
        top_bar.setFixedHeight(44)
        top_bar.setStyleSheet("""
            QFrame { background-color: #0D47A1; border-bottom: 2px solid #1565C0; }
            QLabel { color: white; font-weight: bold; font-size: 12px; }
            QComboBox {
                background-color: #1565C0; color: white; border: 1px solid #42A5F5;
                border-radius: 4px; padding: 4px 24px 4px 8px; font-weight: bold;
                font-size: 12px; min-width: 220px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; border: none; }
            QComboBox QAbstractItemView {
                background-color: #1a1a1a; color: white; selection-background-color: #1565C0;
                border: 1px solid #42A5F5;
            }
        """)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(12, 0, 12, 0)

        lbl_tersane = QLabel("🏗️ AKTİF TERSANE:")
        top_bar_layout.addWidget(lbl_tersane)

        self.combo_tersane_global = QComboBox()
        self._populate_tersane_combo()
        self.combo_tersane_global.currentIndexChanged.connect(self._on_tersane_changed)
        top_bar_layout.addWidget(self.combo_tersane_global)

        # Tersane bilgi etiketi
        self.lbl_tersane_info = QLabel("")
        self.lbl_tersane_info.setStyleSheet("color: #90CAF9; font-size: 11px; font-weight: normal;")
        top_bar_layout.addWidget(self.lbl_tersane_info)
        self._update_tersane_info()

        top_bar_layout.addStretch()

        # Sağ tarafta uygulama bilgisi
        lbl_version = QLabel(f"Puantaj v{__version__}")
        lbl_version.setStyleSheet("color: #64B5F6; font-size: 10px; font-weight: normal;")
        top_bar_layout.addWidget(lbl_version)

        main_layout.addWidget(top_bar)

        # ═══════════════════════════════════════════
        # ANA İÇERİK (Sidebar + Pages)
        # ═══════════════════════════════════════════
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)

        sidebar = QFrame()
        sidebar.setMinimumWidth(220)
        sidebar.setStyleSheet("background-color: #1a1a1a;")
        sb_layout = QVBoxLayout(sidebar)

        title = QLabel("SARAL\nPUANTAJ")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: white; padding: 20px;")
        sb_layout.addWidget(title)

        self.pages = QStackedWidget()
        self.buttons = []

        # Sayfaları oluştur ve tersane_id'yi set et
        self.page_dashboard = DashboardPage(self.signal_manager)
        self.page_upload = UploadPage(self.signal_manager)
        self.page_records = RecordsPage(self.signal_manager)
        self.page_personnel = PersonnelPage(self.signal_manager)
        self.page_avans = AvansPage(self.signal_manager)
        self.page_holidays = HolidaysPage(self.signal_manager)
        self.page_payslip = PayslipPage(self.signal_manager)
        self.page_bes = BesYonetimiPage(self.signal_manager)
        self.page_izin = IzinYonetimiPage(self.signal_manager)
        self.page_raporlar = RaporlarPage(self.signal_manager)
        self.page_settings = SettingsPage(self.signal_manager)

        menus = [
            ("📊 Dashboard", self.page_dashboard),
            ("📥 Veri Yükle", self.page_upload),
            ("✏️ Günlük Kayıtlar", self.page_records),
            ("👥 Personel", self.page_personnel),
            ("💸 Avans/Kesinti", self.page_avans),
            ("📅 Resmi Tatiller", self.page_holidays),
            ("🧾 Bordro Fişi", self.page_payslip),
            ("💰 BES Yönetimi", self.page_bes),
            ("📋 İzin Yönetimi", self.page_izin),
            ("📈 Raporlar", self.page_raporlar),
            ("⚙️ Ayarlar", self.page_settings),
        ]

        for i, (name, widget) in enumerate(menus):
            self.pages.addWidget(widget)
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { text-align: left; padding: 12px; color: #bbb; border: none; font-size: 14px; }
                QPushButton:checked { background-color: #333; color: white; border-left: 4px solid #2196F3; }
                QPushButton:hover { background-color: #252525; }
            """)
            btn.clicked.connect(lambda _, idx=i: self.change_page(idx))
            sb_layout.addWidget(btn)
            self.buttons.append(btn)

        # Yardım butonu
        btn_help = QPushButton("❓ Yardım/Kılavuz")
        btn_help.setStyleSheet("color: #2196F3; font-weight: bold; margin-top: 10px;")
        btn_help.clicked.connect(self.show_help)
        sb_layout.addWidget(btn_help)

        sb_layout.addStretch()
        layout.addWidget(sidebar, 0)
        layout.addWidget(self.pages, 1)

        main_layout.addWidget(body, 1)

        # İlk tersane_id'yi tüm sayfalara gönder
        self._broadcast_tersane_id()

        self.buttons[0].click()

        # Tersane değiştiğinde tüm sayfalara sinyal
        self.signal_manager.tersane_changed.connect(self._on_tersane_signal)

        # Settings sayfası tersane eklediğinde combo'yu yenile
        self.signal_manager.data_updated.connect(self._refresh_tersane_combo_if_needed)

    def _populate_tersane_combo(self):
        """Tersane combobox'ını doldurur."""
        self.combo_tersane_global.blockSignals(True)
        current_id = self.aktif_tersane_id
        self.combo_tersane_global.clear()

        # "Tüm Tersaneler" seçeneği
        self.combo_tersane_global.addItem("🏗️ Tüm Tersaneler", 0)

        tersaneler = self.db.get_tersaneler()
        selected_idx = 0
        for i, t in enumerate(tersaneler):
            label = f"{t[1]}  ({t[2]} - {t[3]})"
            self.combo_tersane_global.addItem(label, t[0])
            if t[0] == current_id:
                selected_idx = i + 1  # +1 for "Tüm Tersaneler"

        self.combo_tersane_global.setCurrentIndex(selected_idx)
        self.combo_tersane_global.blockSignals(False)

    def _on_tersane_changed(self, index):
        """Global tersane combobox değiştiğinde."""
        tersane_id = self.combo_tersane_global.currentData()
        self.aktif_tersane_id = tersane_id if tersane_id else None
        self._update_tersane_info()
        self._broadcast_tersane_id()

    def _update_tersane_info(self):
        """Tersane bilgi etiketini günceller."""
        if not self.aktif_tersane_id:
            self.lbl_tersane_info.setText("Tüm tersanelerin verileri gösteriliyor")
            return
        tersane = self.db.get_tersane(self.aktif_tersane_id)
        if tersane:
            self.lbl_tersane_info.setText(
                f"Giriş: {tersane['en_gec_giris']}  |  Çıkış: {tersane['en_erken_cikis']}  |  "
                f"Mesai: {tersane['mesai_baslangic']}  |  Vardiya: {tersane['vardiya_limit']}"
            )
        else:
            self.lbl_tersane_info.setText("")

    def _broadcast_tersane_id(self):
        """Aktif tersane_id'yi tüm sayfalara gönderir."""
        tid = self.aktif_tersane_id or 0
        current_idx = self.pages.currentIndex()  # NEW: only refresh visible page for lazy loading.
        # set_tersane_id metodu olan tüm sayfalara gönder
        for i in range(self.pages.count()):
            page = self.pages.widget(i)
            if hasattr(page, 'set_tersane_id'):
                try:
                    page.set_tersane_id(tid, refresh=(i == current_idx))  # NEW: refresh only active page to avoid UI stutter.
                except TypeError:
                    page.set_tersane_id(tid)  # SAFE: fallback for pages without refresh parameter.
        # Sinyal de gönder
        self.signal_manager.tersane_changed.emit(tid)

    def _on_tersane_signal(self, tersane_id):
        """Sinyal ile gelen tersane değişikliği."""
        pass  # broadcast zaten yapıldı

    def _refresh_tersane_combo_if_needed(self):
        """Settings sayfasında tersane eklendiğinde combo'yu yeniler."""
        old_count = self.combo_tersane_global.count()
        new_count = len(self.db.get_tersaneler()) + 1  # +1 for "Tüm"
        if old_count != new_count:
            self._populate_tersane_combo()

    def show_help(self):
        from PySide6.QtWidgets import QTextEdit
        import os
        help_path = os.path.join(os.path.dirname(__file__), "KULLANICI_KILAVUZU.md")
        text = "Kılavuz bulunamadı."
        if os.path.exists(help_path):
            with open(help_path, encoding="utf-8") as f:
                text = f.read()
        dlg = QDialog(self)
        dlg.setWindowTitle("Kullanıcı Kılavuzu")
        dlg.resize(600, 500)
        l = QVBoxLayout(dlg)
        edit = QTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(text)
        l.addWidget(edit)
        btn = QPushButton("Kapat")
        btn.clicked.connect(dlg.accept)
        l.addWidget(btn)
        dlg.exec()

    def check_updates(self):
        try:
            update_info = check_for_update()
            if update_info:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("Yeni Güncelleme Mevcut!")
                msg.setText(f"📦 Yeni sürüm mevcut: v{update_info['version']}")
                msg.setInformativeText(f"Şu anki sürüm: v{__version__}\n\nDeğişiklikler:\n{update_info['release_notes'][:200]}...")
                download_btn = msg.addButton("İndir", QMessageBox.AcceptRole)
                msg.addButton("Daha Sonra", QMessageBox.RejectRole)
                msg.setDefaultButton(download_btn)
                msg.exec()

                if msg.clickedButton() == download_btn:
                    import webbrowser
                    webbrowser.open(update_info['release_url'])
        except Exception as e:
            from app_logger import log_error
            log_error(f"Güncelleme kontrolü başarısız: {e}")

    def change_page(self, idx):
        self.pages.setCurrentIndex(idx)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == idx)
        # NEW: lazy-load data for the newly visible page if it was marked dirty.
        try:
            page = self.pages.widget(idx)
            if hasattr(page, 'refresh_if_needed'):
                page.refresh_if_needed()  # WHY: defer heavy loads until page is visible.
        except Exception:
            pass  # SAFEGUARD: page refresh must not crash navigation.

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Theme config
    config = load_config()
    if config.get("theme", "dark") == "dark":
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)
    else:
        app.setStyle("Windows")

    font = app.font()
    font.setPointSize(int(config.get("font_size", 12)))
    app.setFont(font)

    # Login Check
    db = Database()
    db.current_firma_id = 1  # GENEL

    if LoginDialog(db).exec():
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
