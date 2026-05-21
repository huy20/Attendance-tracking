import os
import shutil
import sqlite3
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle, RoundedRectangle

from ui_components import RoundedButton, Card, make_screen_bg


class UserRow(BoxLayout):
    """A styled row card for each registered user."""
    def __init__(self, name, on_delete, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None,
                         height=64, spacing=12, padding=[16, 8], **kwargs)
        with self.canvas.before:
            Color(*get_color_from_hex("#161B22"))
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[12,])
        self.bind(pos=self._upd, size=self._upd)

        # Avatar circle label
        avatar = Label(
            text=name[0].upper(),
            font_size='20sp', bold=True,
            color=get_color_from_hex("#58A6FF"),
            size_hint_x=None, width=44,
        )
        with avatar.canvas.before:
            Color(*get_color_from_hex("#1C2A3A"))
            RoundedRectangle(pos=avatar.pos, size=avatar.size, radius=[22,])
        avatar.bind(pos=lambda w, v: None, size=lambda w, v: None)

        name_lbl = Label(
            text=name.replace("_", " "),
            font_size='17sp', bold=True,
            color=get_color_from_hex("#E6EDF3"),
            halign='left', valign='middle',
        )
        name_lbl.bind(size=name_lbl.setter('text_size'))

        btn_del = RoundedButton(
            text='Delete',
            bg_color=get_color_from_hex("#6E1C1C"),
            size_hint_x=None, width=90, radius=[10,], font_size='14sp',
        )
        btn_del.bind(on_press=lambda x: on_delete(name))

        self.add_widget(avatar)
        self.add_widget(name_lbl)
        self.add_widget(btn_del)

    def _upd(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size


class ViewFacesScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        make_screen_bg(self)

        root = BoxLayout(orientation='vertical', padding=[24, 30, 24, 20], spacing=16)

        # ── Header ───────────────────────────────────────────────────────────
        header_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=48)
        self.title_label = Label(
            text='Registered Users',
            font_size='26sp', bold=True,
            color=get_color_from_hex("#E6EDF3"),
            halign='left', valign='middle',
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        btn_back = RoundedButton(
            text='Back', size_hint_x=None, width=110,
            bg_color=get_color_from_hex("#21262D"), radius=[12,], font_size='15sp',
        )
        btn_back.size_hint_y = None
        btn_back.height = 44
        btn_back.bind(on_press=self.go_back)
        header_row.add_widget(self.title_label)
        header_row.add_widget(btn_back)
        root.add_widget(header_row)

        # ── Count badge ──────────────────────────────────────────────────────
        self.count_label = Label(
            text='',
            font_size='13sp',
            color=get_color_from_hex("#8B949E"),
            size_hint_y=None, height=22,
            halign='left', valign='middle',
        )
        self.count_label.bind(size=self.count_label.setter('text_size'))
        root.add_widget(self.count_label)

        # ── Scrollable user list ──────────────────────────────────────────────
        self.scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        self.scroll.add_widget(self.list_layout)
        root.add_widget(self.scroll)

        self.add_widget(root)

    def on_enter(self, *args):
        self.load_users()

    def load_users(self):
        self.list_layout.clear_widgets()
        app = App.get_running_app()
        base_dir = os.path.join(app.user_data_dir, "registered_faces")
        db_path = os.path.join(base_dir, "faces.db")

        users = []
        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    rows = conn.execute("SELECT DISTINCT person_name FROM user_embeddings ORDER BY person_name ASC").fetchall()
                    users = [row[0] for row in rows if row[0] != "keys"]
            except Exception as e:
                print(f"Error reading faces.db: {e}")

        self.title_label.text = 'Registered Users'
        self.count_label.text = f"{len(users)} user{'s' if len(users) != 1 else ''} registered"

        if users:
            for user in users:
                row = UserRow(name=user, on_delete=self.confirm_delete)
                self.list_layout.add_widget(row)
        else:
            empty = Label(
                text="No users registered yet.\nRegister a face to get started.",
                font_size='16sp',
                color=get_color_from_hex("#484F58"),
                halign='center', valign='middle',
                size_hint_y=None, height=100,
            )
            empty.bind(size=empty.setter('text_size'))
            self.list_layout.add_widget(empty)

    def confirm_delete(self, user_folder):
        display = user_folder.replace("_", " ")

        content = BoxLayout(orientation='vertical', padding=20, spacing=14)
        with content.canvas.before:
            Color(*get_color_from_hex("#161B22"))
            Rectangle(pos=content.pos, size=content.size)

        msg = Label(
            text=f"Delete [b]{display}[/b]?\n\nThis cannot be undone.",
            markup=True,
            font_size='16sp',
            color=get_color_from_hex("#E6EDF3"),
            halign='center', valign='middle',
        )
        msg.bind(size=msg.setter('text_size'))
        content.add_widget(msg)

        btns = BoxLayout(orientation='horizontal', spacing=12, size_hint_y=None, height=50)
        btn_yes = RoundedButton(
            text='Yes, Delete',
            bg_color=get_color_from_hex("#6E1C1C"), radius=[12,],
        )
        btn_no = RoundedButton(
            text='Cancel',
            bg_color=get_color_from_hex("#21262D"), radius=[12,],
        )
        btns.add_widget(btn_yes)
        btns.add_widget(btn_no)
        content.add_widget(btns)

        popup = Popup(
            title='Confirm Deletion',
            title_color=get_color_from_hex("#F85149"),
            content=content,
            size_hint=(0.85, 0.42),
            auto_dismiss=False,
            background_color=get_color_from_hex("#0D1117"),
        )
        btn_no.bind(on_press=popup.dismiss)
        btn_yes.bind(on_press=lambda x: [self.execute_delete(user_folder), popup.dismiss()])
        popup.open()

    def execute_delete(self, user_folder):
        app = App.get_running_app()
        base_dir = os.path.join(app.user_data_dir, "registered_faces")
        db_path = os.path.join(base_dir, "faces.db")
        user_dir = os.path.join(base_dir, user_folder)

        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.execute("DELETE FROM user_embeddings WHERE person_name = ?", (user_folder,))
                    conn.commit()
            except Exception as e:
                print(f"DB delete error: {e}")

        if os.path.exists(user_dir):
            try:
                shutil.rmtree(user_dir)
            except Exception as e:
                print(f"Folder delete error: {e}")

        if hasattr(app, 'syncer') and app.syncer:
            app.syncer.push_delete(user_folder)

        self.load_users()

    def go_back(self, *args):
        self.manager.current = 'main_menu'