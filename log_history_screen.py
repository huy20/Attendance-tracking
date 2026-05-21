import os
import sqlite3
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.utils import platform, get_color_from_hex
from kivy.graphics import Color, Rectangle, RoundedRectangle

from ui_components import RoundedButton, Card, make_screen_bg
from network_sync import AttendanceSyncer


def _col_header(text):
    lbl = Label(
        text=text, bold=True, font_size='15sp',
        color=get_color_from_hex("#58A6FF"),
        size_hint_y=None, height=38,
        halign='left', valign='middle',
    )
    lbl.bind(size=lbl.setter('text_size'))
    return lbl


def _row_cell(text, even=False):
    bg = get_color_from_hex("#161B22") if even else get_color_from_hex("#0D1117")
    lbl = Label(
        text=text, font_size='14sp',
        color=get_color_from_hex("#C9D1D9"),
        size_hint_y=None, height=36,
        halign='left', valign='middle',
    )
    lbl.bind(size=lbl.setter('text_size'))
    return lbl


class LogHistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        make_screen_bg(self)

        root = BoxLayout(orientation='vertical', padding=[24, 30, 24, 20], spacing=16)

        # ── Header ───────────────────────────────────────────────────────────
        header_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=48)
        self.header_label = Label(
            text="Today's Attendance",
            font_size='26sp', bold=True,
            color=get_color_from_hex("#E6EDF3"),
            halign='left', valign='middle',
        )
        self.header_label.bind(size=self.header_label.setter('text_size'))
        btn_back = RoundedButton(
            text='Back', size_hint_x=None, width=110, height=44,
            bg_color=get_color_from_hex("#21262D"), radius=[12,], font_size='15sp',
        )
        btn_back.size_hint_y = None
        btn_back.bind(on_press=self.go_back)
        header_row.add_widget(self.header_label)
        header_row.add_widget(btn_back)
        root.add_widget(header_row)

        # ── Attendance Table Card ─────────────────────────────────────────────
        table_card = Card(orientation='vertical', padding=[16, 12], spacing=0,
                          size_hint_y=0.45, bg_color=get_color_from_hex("#161B22"))

        col_header = BoxLayout(size_hint_y=None, height=38, spacing=10)
        col_header.add_widget(_col_header("Name"))
        col_header.add_widget(_col_header("Time"))
        table_card.add_widget(col_header)

        # thin divider
        div = BoxLayout(size_hint_y=None, height=1)
        with div.canvas:
            Color(*get_color_from_hex("#30363D"))
            Rectangle(size=div.size, pos=div.pos)
        div.bind(pos=lambda w, v: None, size=lambda w, v: None)
        table_card.add_widget(div)

        self.scroll = ScrollView()
        self.grid = GridLayout(cols=2, spacing=[10, 2], size_hint_y=None, padding=[0, 6])
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        table_card.add_widget(self.scroll)
        root.add_widget(table_card)

        # ── Gateway Card ──────────────────────────────────────────────────────
        gw_card = Card(orientation='vertical', padding=[16, 14], spacing=12,
                       size_hint_y=None, height=200,
                       bg_color=get_color_from_hex("#161B22"))

        gw_title = Label(
            text='Gateway Configuration',
            font_size='15sp', bold=True,
            color=get_color_from_hex("#8B949E"),
            size_hint_y=None, height=24,
            halign='left', valign='middle',
        )
        gw_title.bind(size=gw_title.setter('text_size'))
        gw_card.add_widget(gw_title)

        # IP row
        ip_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=46, spacing=10)
        self.ip_input = TextInput(
            hint_text='https://192.168.x.x:5100',
            multiline=False, font_size='15sp',
            background_color=get_color_from_hex("#0D1117"),
            foreground_color=get_color_from_hex("#E6EDF3"),
            hint_text_color=get_color_from_hex("#484F58"),
            cursor_color=get_color_from_hex("#58A6FF"),
            padding=[12, 10],
        )
        self.btn_toggle = RoundedButton(
            text='Auto-Sync: OFF',
            bg_color=get_color_from_hex("#21262D"),
            size_hint_x=None, width=150, radius=[12,], font_size='14sp',
        )
        self.btn_toggle.bind(on_press=self.toggle_auto_sync)
        ip_row.add_widget(self.ip_input)
        ip_row.add_widget(self.btn_toggle)
        gw_card.add_widget(ip_row)

        # Action row
        action_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=46, spacing=10)
        btn_sync = RoundedButton(
            text='Sync Now',
            bg_color=get_color_from_hex("#1F6FEB"), radius=[12,], font_size='15sp',
        )
        btn_sync.bind(on_press=self.manual_sync)
        self.btn_export = RoundedButton(
            text='Export Key',
            bg_color=get_color_from_hex("#B08800"), radius=[12,], font_size='15sp',
        )
        self.btn_export.bind(on_press=self.export_key)
        
        self.btn_reset = RoundedButton(
            text='Reset Key',
            bg_color=get_color_from_hex("#6E1C1C"), radius=[12,], font_size='15sp',
        )
        self.btn_reset.bind(on_press=self.reset_key)

        action_row.add_widget(btn_sync)
        action_row.add_widget(self.btn_export)
        action_row.add_widget(self.btn_reset)
        gw_card.add_widget(action_row)

        # Status label
        self.lbl_status = Label(
            text='', font_size='13sp',
            color=get_color_from_hex("#8B949E"),
            size_hint_y=None, height=22,
            halign='left', valign='middle',
        )
        self.lbl_status.bind(size=self.lbl_status.setter('text_size'))
        gw_card.add_widget(self.lbl_status)

        root.add_widget(gw_card)
        self.add_widget(root)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def on_enter(self):
        self.load_todays_logs()
        self._sync_toggle_ui()

    def load_todays_logs(self):
        self.grid.clear_widgets()
        try:
            app = App.get_running_app()
            base_dir = os.path.join(app.user_data_dir, "registered_faces")
            db_path = os.path.join(base_dir, 'attendance.db')
            if not os.path.exists(db_path):
                self.header_label.text = "No attendance records yet"
                return

            with sqlite3.connect(db_path) as conn:
                today = datetime.now().strftime("%Y-%m-%d")
                rows = conn.execute(
                    f"SELECT person_name, timestamp FROM attendance_logs "
                    f"WHERE timestamp LIKE '{today}%' ORDER BY timestamp DESC"
                ).fetchall()

            self.header_label.text = f"Today's Attendance  •  {len(rows)} records"
            for i, (name, ts) in enumerate(rows):
                time_only = ts.split(" ")[1][:5] if " " in ts else ts
                self.grid.add_widget(_row_cell(name, even=(i % 2 == 0)))
                self.grid.add_widget(_row_cell(time_only, even=(i % 2 == 0)))

            if not rows:
                self.grid.cols = 1
                empty = Label(text="No records for today", font_size='14sp',
                              color=get_color_from_hex("#484F58"),
                              size_hint_y=None, height=40)
                self.grid.add_widget(empty)
                self.grid.cols = 2
        except Exception as e:
            self.header_label.text = f"Error: {e}"

    def _get_url(self):
        ip = self.ip_input.text.strip()
        if not ip:
            return None
        return ip if ip.startswith("http") else f"https://{ip}"

    def _ensure_syncer(self, url=None):
        app = App.get_running_app()
        if url is None:
            url = self._get_url() or "https://127.0.0.1:5100"
        if not hasattr(app, 'syncer') or app.syncer is None:
            base_dir = os.path.join(app.user_data_dir, "registered_faces")
            app.syncer = AttendanceSyncer(base_dir=base_dir, host_url=url)
        else:
            base = url.rstrip("/")
            app.syncer.gateway_url      = base
            app.syncer.attendance_url   = f"{base}/sync"
            app.syncer.faces_version_url = f"{base}/faces/version"
            app.syncer.faces_download_url = f"{base}/faces/download"
            app.syncer.faces_upload_url  = f"{base}/faces/upload"
            app.syncer.faces_delete_url  = f"{base}/faces/delete"
        return app.syncer

    def _sync_toggle_ui(self):
        app = App.get_running_app()
        on = hasattr(app, 'syncer') and app.syncer and app.syncer.event
        self.btn_toggle.text = "Auto-Sync: ON" if on else "Auto-Sync: OFF"
        self.btn_toggle.bg_color = (
            get_color_from_hex("#1B4332") if on else get_color_from_hex("#21262D")
        )
        self.btn_toggle.update_rect()

    def manual_sync(self, *args):
        url = self._get_url()
        if not url:
            self.lbl_status.text = "⚠  Enter gateway IP first."
            self.lbl_status.color = get_color_from_hex("#F85149")
            return
        syncer = self._ensure_syncer(url)
        syncer.sync_with_host(0)
        self.lbl_status.text = "✔  Sync triggered in background."
        self.lbl_status.color = get_color_from_hex("#3FB950")

    def toggle_auto_sync(self, *args):
        url = self._get_url()
        if not url:
            self.lbl_status.text = "⚠  Enter gateway IP first."
            self.lbl_status.color = get_color_from_hex("#F85149")
            return
        syncer = self._ensure_syncer(url)
        if syncer.event:
            syncer.stop_syncing()
            self.lbl_status.text = "Auto-sync stopped."
            self.lbl_status.color = get_color_from_hex("#8B949E")
        else:
            syncer.start_syncing()
            self.lbl_status.text = "✔  Auto-sync started."
            self.lbl_status.color = get_color_from_hex("#3FB950")
        self._sync_toggle_ui()

    def reset_key(self, *args):
        syncer = self._ensure_syncer()
        syncer.reset_keys()
        self.lbl_status.text = "✔  New keys generated. Please export again."
        self.lbl_status.color = get_color_from_hex("#3FB950")

    def export_key(self, *args):
        app = App.get_running_app()
        base_dir = os.path.join(app.user_data_dir, "registered_faces")
        syncer = self._ensure_syncer()

        if platform == 'android':
            try:
                from android.storage import primary_external_storage_path
                export_dir = os.path.join(primary_external_storage_path(), "Download")
            except Exception:
                export_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        else:
            export_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        ok, msg = syncer.export_public_key(export_dir)
        if ok:
            self.lbl_status.text = f"✔  Key saved → {export_dir}"
            self.lbl_status.color = get_color_from_hex("#3FB950")
        else:
            self.lbl_status.text = f"✘  {msg}"
            self.lbl_status.color = get_color_from_hex("#F85149")

    def go_back(self, *args):
        self.manager.current = 'main_menu'