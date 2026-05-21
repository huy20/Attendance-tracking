import os
os.environ['OPENCV_SKIP_BOOTSTRAP_CONFIG'] = '1'

import cv2
import numpy as np
import threading
import glob
import time
import sqlite3
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.camera import Camera
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.clock import Clock, mainthread
from kivy.graphics.texture import Texture
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.utils import platform, get_color_from_hex

from face_register import FaceRegister
from face_recognition import FaceEmbedder
from ui_components import RoundedButton, make_screen_bg


# ── Styled popup for name entry ────────────────────────────────────────────────
def _make_name_popup(on_start, on_cancel):
    content = BoxLayout(orientation='vertical', padding=20, spacing=14)
    with content.canvas.before:
        Color(*get_color_from_hex("#161B22"))
        bg = Rectangle(pos=content.pos, size=content.size)
    content.bind(pos=lambda w, v: setattr(bg, 'pos', v),
                 size=lambda w, v: setattr(bg, 'size', v))

    title = Label(
        text='New Face Registration',
        font_size='18sp', bold=True,
        color=get_color_from_hex("#E6EDF3"),
        size_hint_y=None, height=30,
        halign='left', valign='middle',
    )
    title.bind(size=title.setter('text_size'))

    hint = Label(
        text='Enter the person\'s name or employee ID.\nUse underscores instead of spaces.',
        font_size='13sp',
        color=get_color_from_hex("#8B949E"),
        size_hint_y=None, height=44,
        halign='left', valign='middle',
    )
    hint.bind(size=hint.setter('text_size'))

    name_input = TextInput(
        hint_text='e.g. John_Doe or EMP001',
        multiline=False,
        font_size='16sp',
        size_hint_y=None, height=46,
        background_color=get_color_from_hex("#0D1117"),
        foreground_color=get_color_from_hex("#E6EDF3"),
        hint_text_color=get_color_from_hex("#484F58"),
        cursor_color=get_color_from_hex("#58A6FF"),
        padding=[12, 10],
    )

    btns = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=12)
    btn_cancel = RoundedButton(
        text='Cancel',
        bg_color=get_color_from_hex("#21262D"), radius=[12,],
    )
    btn_start = RoundedButton(
        text='Start',
        bg_color=get_color_from_hex("#1F6FEB"), radius=[12,],
    )

    btns.add_widget(btn_cancel)
    btns.add_widget(btn_start)

    content.add_widget(title)
    content.add_widget(hint)
    content.add_widget(name_input)
    content.add_widget(btns)

    popup = Popup(
        title='',
        title_size='1sp',
        content=content,
        size_hint=(0.9, 0.52),
        auto_dismiss=False,
        background_color=get_color_from_hex("#0D1117"),
        separator_height=0,
    )

    btn_cancel.bind(on_press=lambda x: on_cancel(popup))
    btn_start.bind(on_press=lambda x: on_start(popup, name_input.text.strip()))

    return popup


# ─────────────────────────────────────────────────────────────────────────────
class FaceRegistrationScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        make_screen_bg(self)

        self.layout = BoxLayout(orientation='vertical', padding=[0, 0], spacing=0)

        # ── Camera feed ──────────────────────────────────────────────────────
        self.image_widget = Image(allow_stretch=True, keep_ratio=True)
        self.layout.add_widget(self.image_widget)

        # ── HUD overlay at the bottom ─────────────────────────────────────────
        hud = BoxLayout(orientation='vertical', size_hint_y=None, height=130,
                        padding=[20, 10], spacing=8)
        with hud.canvas.before:
            Color(0, 0, 0, 0.70)
            self._hud_bg = Rectangle(pos=hud.pos, size=hud.size)
        hud.bind(pos=lambda w, v: setattr(self._hud_bg, 'pos', v),
                 size=lambda w, v: setattr(self._hud_bg, 'size', v))

        # Progress bar (thin, accent colour)
        self.progress_bar = ProgressBar(
            max=1.0, value=0, size_hint_y=None, height=6,
        )

        status_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=36)
        self.status_label = Label(
            text='Initializing…',
            font_size='16sp', bold=True,
            color=get_color_from_hex("#58A6FF"),
            halign='left', valign='middle',
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        self.count_label = Label(
            text='0 / 5',
            font_size='15sp',
            color=get_color_from_hex("#8B949E"),
            size_hint_x=None, width=80,
            halign='right', valign='middle',
        )
        self.count_label.bind(size=self.count_label.setter('text_size'))
        status_row.add_widget(self.status_label)
        status_row.add_widget(self.count_label)

        name_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=34)
        self.name_display = Label(
            text='',
            font_size='14sp',
            color=get_color_from_hex("#8B949E"),
            halign='left', valign='middle',
        )
        self.name_display.bind(size=self.name_display.setter('text_size'))
        btn_back = RoundedButton(
            text='Cancel',
            bg_color=get_color_from_hex("#6E1C1C"),
            size_hint_x=None, width=120, radius=[10,], font_size='14sp',
        )
        btn_back.bind(on_press=self._cancel)
        name_row.add_widget(self.name_display)
        name_row.add_widget(btn_back)

        hud.add_widget(self.progress_bar)
        hud.add_widget(status_row)
        hud.add_widget(name_row)
        self.layout.add_widget(hud)

        self.add_widget(self.layout)

        # ── State ────────────────────────────────────────────────────────────
        self.person_name = "User_001"
        self.last_saved_count = 0
        self.booth = None
        self.cam = None
        self.last_ai_time = 0
        self.ai_interval = 0.2
        self.latest_result = {
            "status": "WAITING", "reasons": [], "progress": 0,
            "count": 0, "max_shots": 5,
        }
        self.embedder = FaceEmbedder("MobileFaceNet.onnx")

    # ── Screen lifecycle ──────────────────────────────────────────────────────

    def on_enter(self, *args):
        app = App.get_running_app()
        self.base_dir = os.path.join(app.user_data_dir, "registered_faces")
        self._show_name_popup()

    def on_leave(self, *args):
        if hasattr(self, 'event'):
            self.event.cancel()
            del self.event
        if self.cam:
            self.cam.play = False
            self.layout.remove_widget(self.cam)
            self.cam = None

    # ── Name popup ────────────────────────────────────────────────────────────

    def _show_name_popup(self):
        self.popup = _make_name_popup(
            on_start=self._on_popup_start,
            on_cancel=self._on_popup_cancel,
        )
        self.popup.open()

    def _on_popup_cancel(self, popup):
        popup.dismiss()
        self.manager.current = 'main_menu'

    def _on_popup_start(self, popup, text):
        if not text:
            return
        self.person_name = text.replace(" ", "_")
        self.person_dir = os.path.join(self.base_dir, self.person_name)
        os.makedirs(self.person_dir, exist_ok=True)
        popup.dismiss()
        self.name_display.text = f"Registering: {self.person_name.replace('_', ' ')}"
        self._ask_permissions()

    # ── Permissions → start ───────────────────────────────────────────────────

    def _ask_permissions(self):
        self.status_label.text = "Requesting camera…"
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            def cb(perms, results):
                if all(results):
                    Clock.schedule_once(lambda dt: self._start_camera(), 0.1)
                else:
                    self.status_label.text = "Camera permission denied."
                    self.status_label.color = get_color_from_hex("#F85149")
            request_permissions([Permission.CAMERA], cb)
        else:
            self._start_camera()

    def _start_camera(self):
        self.status_label.text = "Starting camera…"
        try:
            if not self.booth:
                self.booth = FaceRegister()
            self.booth.COOLDOWN = 0.2
            self.booth.MAX_SHOTS = 5
            self.booth.STABILITY_THRESHOLD = 18
            self.booth.reset_session()

            if not self.cam:
                self.cam = Camera(resolution=(640, 480), play=True, index=0)
                self.cam.opacity = 0
                self.cam.size_hint = (0, 0)
                self.layout.add_widget(self.cam)

            if not hasattr(self, 'event'):
                self.event = Clock.schedule_interval(self.update, 1.0 / 30.0)
        except Exception as e:
            self.status_label.text = f"Camera Error: {e}"
            self.status_label.color = get_color_from_hex("#F85149")

    # ── Main update loop ──────────────────────────────────────────────────────

    def update(self, dt):
        if not self.cam or not self.cam.texture or not self.booth:
            return

        pixels = self.cam.texture.pixels
        w, h = self.cam.texture.size
        raw = np.frombuffer(pixels, dtype=np.uint8).reshape((h, w, 4))
        frame = cv2.rotate(raw, cv2.ROTATE_90_CLOCKWISE)
        frame = cv2.flip(frame, 1)

        now = time.time()
        if now - self.last_ai_time >= self.ai_interval:
            self.last_ai_time = now
            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            bgr = cv2.cvtColor(small, cv2.COLOR_RGBA2BGR)
            try:
                self.latest_result = self.booth.run(bgr)
            except Exception as e:
                print(f"AI error: {e}")

        result = self.latest_result
        reason = f"  –  {result['reasons'][0]}" if result.get('reasons') else ""
        status = result.get('status', 'WAITING')

        # Status colour coding
        color_map = {
            'STABLE': "#3FB950", 'STABILIZING': "#58A6FF",
            'INVALID': "#F85149", 'NO FACE': "#8B949E",
            'COMPLETE': "#3FB950", 'WAITING': "#8B949E",
        }
        self.status_label.text = f"{status}{reason}"
        self.status_label.color = get_color_from_hex(color_map.get(status, "#8B949E"))
        self.count_label.text = f"{result.get('count', 0)} / {result.get('max_shots', 5)}"
        self.progress_bar.value = result.get('progress', 0)

        # Save captured face
        current_count = result.get('count', 0)
        if current_count > self.last_saved_count:
            ts = int(time.time() * 1000)
            path = os.path.join(self.person_dir, f"face_{current_count}_{ts}.jpg")
            cv2.imwrite(path, result['captured_face'])
            self.last_saved_count = current_count

        # Trigger embedding generation
        if current_count >= result.get('max_shots', 5) and not hasattr(self, '_processing'):
            self._processing = True
            self._start_embedding()
            return

        # Render frame
        h2, w2, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        buf = cv2.flip(rgb, 0).tobytes()
        if not self.image_widget.texture or self.image_widget.texture.size != (w2, h2):
            self.image_widget.texture = Texture.create(size=(w2, h2), colorfmt='rgb')
        self.image_widget.texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
        self.image_widget.canvas.ask_update()

    # ── Embedding generation ──────────────────────────────────────────────────

    def _start_embedding(self):
        if hasattr(self, 'event'):
            self.event.cancel()
        if self.cam:
            self.cam.play = False
        self.status_label.text = "Generating embeddings…"
        self.status_label.color = get_color_from_hex("#58A6FF")
        self.progress_bar.value = 0
        t = threading.Thread(target=self._embedding_task, daemon=True)
        t.start()

    def _embedding_task(self):
        db_path = os.path.join(self.base_dir, "faces.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_embeddings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                person_name   TEXT,
                embedding     BLOB,
                device_id     TEXT    DEFAULT 'android_device_1',
                registered_at TEXT    DEFAULT CURRENT_TIMESTAMP,
                synced        INTEGER DEFAULT 0
            )
        ''')
        for col, defn in [
            ("device_id",     "TEXT DEFAULT 'android_device_1'"),
            ("registered_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("synced",        "INTEGER DEFAULT 0"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE user_embeddings ADD COLUMN {col} {defn}")
            except Exception:
                pass
        conn.commit()

        image_paths = glob.glob(os.path.join(self.person_dir, "*.jpg"))
        all_embs = []
        total = len(image_paths)

        if total == 0:
            self._finish_embedding()
            conn.close()
            return

        for i, p in enumerate(image_paths):
            img = cv2.imread(p)
            vec = self.embedder.get_embedding(img)
            all_embs.append(vec)
            self._update_progress((i + 1) / total)

        chunk_size = 5
        saved = 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i in range(0, len(all_embs), chunk_size):
            chunk = np.array(all_embs[i:i + chunk_size])
            avg = np.mean(chunk, axis=0).astype(np.float32)
            blob = avg.tobytes()
            cursor.execute(
                "INSERT INTO user_embeddings (person_name, embedding, device_id, registered_at, synced) "
                "VALUES (?, ?, ?, ?, 0)",
                (self.person_name, blob, 'android_device_1', now_str)
            )
            saved += 1

        conn.commit()
        conn.close()
        print(f"Saved {saved} embeddings for {self.person_name}")
        self._finish_embedding()

    @mainthread
    def _update_progress(self, value):
        self.progress_bar.value = value

    @mainthread
    def _finish_embedding(self):
        self.status_label.text = "✔  Registration complete!"
        self.status_label.color = get_color_from_hex("#3FB950")
        self.progress_bar.value = 1.0

        app = App.get_running_app()
        if hasattr(app, 'syncer') and app.syncer:
            app.syncer.sync_with_host(0)

        Clock.schedule_once(self._go_home, 2.5)

    def _go_home(self, dt):
        if hasattr(self, '_processing'):
            del self._processing
        self.last_saved_count = 0
        self.progress_bar.value = 0
        self.count_label.text = "0 / 5"
        self.status_label.text = "Initializing…"
        self.status_label.color = get_color_from_hex("#58A6FF")
        self.name_display.text = ""
        if self.booth:
            self.booth.reset_session()
        if self.cam:
            self.cam.play = False
        if self.manager:
            self.manager.current = 'main_menu'

    def _cancel(self, *args):
        self._go_home(None)