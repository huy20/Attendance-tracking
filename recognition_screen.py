import os
import cv2
import numpy as np
import time
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.camera import Camera
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.utils import platform, get_color_from_hex

from face_register import FaceRegister
from face_recognition import FaceEmbedder
from ui_components import RoundedButton, make_screen_bg


class StatusBar(BoxLayout):
    """Bottom HUD bar showing recognition status."""
    def __init__(self, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, None), height=72,
            padding=[20, 10], spacing=16,
            **kwargs
        )
        with self.canvas.before:
            Color(0, 0, 0, 0.65)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        # Status dot indicator
        self.dot = Label(
            text='●',
            font_size='20sp',
            color=get_color_from_hex("#484F58"),
            size_hint_x=None, width=30,
            halign='center', valign='middle',
        )

        # Name + confidence
        self.name_label = Label(
            text='Searching for face…',
            font_size='18sp', bold=True,
            color=get_color_from_hex("#C9D1D9"),
            halign='left', valign='middle',
        )
        self.name_label.bind(size=self.name_label.setter('text_size'))

        self.conf_label = Label(
            text='',
            font_size='14sp',
            color=get_color_from_hex("#8B949E"),
            size_hint_x=None, width=80,
            halign='right', valign='middle',
        )
        self.conf_label.bind(size=self.conf_label.setter('text_size'))

        btn_back = RoundedButton(
            text='Exit',
            bg_color=get_color_from_hex("#6E1C1C"),
            size_hint_x=None, width=90, radius=[10,], font_size='14sp',
        )
        btn_back.bind(on_press=self.go_back_cb)
        self._back_btn = btn_back

        self.add_widget(self.dot)
        self.add_widget(self.name_label)
        self.add_widget(self.conf_label)
        self.add_widget(btn_back)

    def set_back_callback(self, cb):
        self._back_btn.unbind(on_press=self.go_back_cb)
        self._back_btn.bind(on_press=cb)

    def go_back_cb(self, *args):
        pass

    def _upd(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def show_recognized(self, name, conf):
        self.dot.color = get_color_from_hex("#3FB950")
        self.name_label.text = name.replace("_", " ")
        self.name_label.color = get_color_from_hex("#3FB950")
        self.conf_label.text = f"{conf*100:.1f}%"
        self.conf_label.color = get_color_from_hex("#3FB950")

    def show_searching(self):
        self.dot.color = get_color_from_hex("#484F58")
        self.name_label.text = "Searching for face…"
        self.name_label.color = get_color_from_hex("#8B949E")
        self.conf_label.text = ""

    def show_warning(self, message):
        self.dot.color = get_color_from_hex("#F85149")
        self.name_label.text = f"⚠  {message}"
        self.name_label.color = get_color_from_hex("#F85149")
        self.conf_label.text = ""


class FaceRecognitionScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        make_screen_bg(self)

        # FloatLayout so sleep curtain can overlay everything
        self.float = FloatLayout()

        # Main content
        self.content = BoxLayout(orientation='vertical')

        # Camera feed
        self.image_widget = Image(allow_stretch=True, keep_ratio=True)
        self.content.add_widget(self.image_widget)

        # Status HUD bar at bottom
        self.status_bar = StatusBar(pos_hint={'x': 0, 'y': 0})
        self.status_bar.set_back_callback(self.go_back)
        self.content.add_widget(self.status_bar)

        self.float.add_widget(self.content)

        # Sleep curtain (hidden by default, moved off-screen)
        self.sleep_curtain = Button(
            text='[ System Sleeping ]\nTap or step in front to wake',
            markup=False,
            background_normal='',
            background_color=(0, 0, 0, 1),
            color=get_color_from_hex("#30363D"),
            font_size='22sp',
            size_hint=(None, None),
            size=(0, 0),
            pos=(-2000, -2000),
            opacity=0,
        )
        self.sleep_curtain.bind(on_press=self.wake_up)
        self.float.add_widget(self.sleep_curtain)

        self.add_widget(self.float)

        # ── AI state ──────────────────────────────────────────────────────────
        self.booth = None
        self.cam = None
        self.embedder = FaceEmbedder("MobileFaceNet.onnx")
        self.is_sleeping = False
        self._ai_interval = 0.12
        self._last_ai = 0
        self.active_user = None
        self.user_conf = 0.0
        self.persistence = 0
        self.recently_logged = {}
        self.log_cooldown = 10.0
        self.tracking_name = None
        self.consecutive = 0
        self.REQUIRED = 3
        self.latest_status = 'WAITING'
        self.latest_reasons = []

    # ── Sleep / Wake ──────────────────────────────────────────────────────────

    def enter_sleep_mode(self):
        self.is_sleeping = True
        self.sleep_curtain.size_hint = (1, 1)
        self.sleep_curtain.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        self.sleep_curtain.opacity = 1

    def wake_up(self, *args):
        if not self.is_sleeping:
            return
        self.is_sleeping = False
        self.sleep_curtain.size_hint = (None, None)
        self.sleep_curtain.size = (0, 0)
        self.sleep_curtain.pos_hint = {}
        self.sleep_curtain.pos = (-2000, -2000)
        self.sleep_curtain.opacity = 0
        app = App.get_running_app()
        if app and hasattr(app, '_reset_timer'):
            app._reset_timer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        app = App.get_running_app()
        base_dir = os.path.join(app.user_data_dir, "registered_faces")
        os.makedirs(base_dir, exist_ok=True)
        self.db_path = os.path.join(base_dir, "faces.db")
        self.embedder.load_database(base_dir)
        if os.path.exists(self.db_path):
            self.last_db_mtime = os.path.getmtime(self.db_path)
        else:
            self.last_db_mtime = 0
        self._ask_permissions()

    def _ask_permissions(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            def cb(perms, results):
                if all(results):
                    Clock.schedule_once(lambda dt: self._start(), 0.1)
            request_permissions([Permission.CAMERA], cb)
        else:
            self._start()

    def _start(self):
        try:
            if not self.booth:
                self.booth = FaceRegister()
            self.booth.STABILITY_THRESHOLD = 1
            self.booth.COOLDOWN = 0.0
            self.booth.MAX_SHOTS = 999999

            if not self.cam:
                self.cam = Camera(resolution=(640, 480), play=True, index=0)
                self.cam.opacity = 0
                self.cam.size_hint = (0, 0)
                self.content.add_widget(self.cam)

            Clock.unschedule(self._update)
            self.event = Clock.schedule_interval(self._update, 1.0 / 30.0)
        except Exception as e:
            print(f"Recognition start error: {e}")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _update(self, dt):
        if not self.cam or not self.cam.texture:
            return

        pixels = self.cam.texture.pixels
        w, h = self.cam.texture.size
        raw = np.frombuffer(pixels, dtype=np.uint8).reshape((h, w, 4))
        frame = cv2.rotate(raw, cv2.ROTATE_90_CLOCKWISE)
        frame = cv2.flip(frame, 1)

        now = time.time()
        if now - self._last_ai > self._ai_interval:
            self._last_ai = now
            self._run_ai(frame, now)

        if not self.is_sleeping:
            self._update_hud()
            self._render(frame)

    def _run_ai(self, frame, now):
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            try:
                mtime = os.path.getmtime(self.db_path)
                if mtime != getattr(self, 'last_db_mtime', 0):
                    print(f"Database modified (mtime: {mtime}). Reloading known faces...")
                    app = App.get_running_app()
                    base_dir = os.path.join(app.user_data_dir, "registered_faces")
                    self.embedder.load_database(base_dir)
                    self.last_db_mtime = mtime
            except Exception as e:
                print(f"Error checking/reloading face database: {e}")

        try:
            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            bgr = cv2.cvtColor(small, cv2.COLOR_RGBA2BGR)
            result = self.booth.run(bgr)
            self.latest_status = result.get('status', 'WAITING')
            self.latest_reasons = result.get('reasons', [])
            face = result.get('captured_face')

            if face is not None:
                if self.is_sleeping:
                    self.wake_up()
                    return
                app = App.get_running_app()
                if app and hasattr(app, '_reset_timer'):
                    app._reset_timer()

                crop = cv2.resize(face, (112, 112))
                name, conf = self.embedder.recognize(crop)

                if name != "Unknown":
                    if name == self.tracking_name:
                        self.consecutive += 1
                    else:
                        self.tracking_name = name
                        self.consecutive = 1
                    self.active_user = name
                    self.user_conf = conf
                    self.persistence = 12

                    if self.consecutive >= self.REQUIRED:
                        last = self.recently_logged.get(name, 0)
                        if now - last > self.log_cooldown:
                            self.embedder.log_recognition(name)
                            self.recently_logged[name] = now
                else:
                    self.tracking_name = None
                    self.consecutive = 0
                    self._decay()
            else:
                self.tracking_name = None
                self.consecutive = 0
                self._decay()
        except Exception as e:
            print(f"AI error: {e}")

    def _decay(self):
        if self.persistence > 0:
            self.persistence -= 1
        else:
            self.active_user = None

    def _update_hud(self):
        if self.active_user:
            self.status_bar.show_recognized(self.active_user, self.user_conf)
        elif getattr(self, 'latest_status', '') == 'INVALID' and getattr(self, 'latest_reasons', []):
            self.status_bar.show_warning(self.latest_reasons[0])
        else:
            self.status_bar.show_searching()

    def _render(self, frame):
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        buf = cv2.flip(rgb, 0).tobytes()
        if not self.image_widget.texture or self.image_widget.texture.size != (w, h):
            self.image_widget.texture = Texture.create(size=(w, h), colorfmt='rgb')
        self.image_widget.texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def go_back(self, *args):
        self._cleanup()
        self.manager.current = 'main_menu'

    def on_leave(self, *args):
        self._cleanup()

    def _cleanup(self):
        if hasattr(self, 'event'):
            Clock.unschedule(self.event)
        if self.cam:
            self.cam.play = False
            self.content.remove_widget(self.cam)
            self.cam = None
        if self.booth:
            self.booth.reset_session()
        self.image_widget.texture = None