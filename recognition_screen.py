import os
import cv2
import numpy as np
import time
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.camera import Camera
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.utils import platform

from face_register import FaceRegister
from face_recognition import FaceEmbedder

class FaceRecognitionScreen(Screen):
    def __init__(self, **kwargs):
        super(FaceRecognitionScreen, self).__init__(**kwargs)
        
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        self.image_widget = Image(allow_stretch=True, keep_ratio=True)
        self.status_label = Label(text="Initializing...", size_hint_y=None, height=40, font_size=20)
        
        btn_back = Button(text="Stop & Go Back", size_hint_y=None, height=60)
        btn_back.bind(on_release=self.go_back)

        self.layout.add_widget(self.image_widget)
        self.layout.add_widget(self.status_label)
        self.layout.add_widget(btn_back)
        self.add_widget(self.layout)
        
        self.booth = None
        self.cam = None
        self.embedder = FaceEmbedder("MobileFaceNet.onnx")
        
        self.last_ai_time = 0
        self.ai_interval = 0.12
        
        self.active_user = None
        self.user_confidence = 0
        self.persistence_frames = 0
        self.recently_logged = {} 
        self.log_cooldown = 10.0
        
        # --- Tracker Variables ---
        self.tracking_name = None
        self.consecutive_matches = 0
        self.REQUIRED_MATCHES = 3  # The AI must guess the SAME name 3 times in a row

    def on_enter(self, *args):
        app = App.get_running_app()
        base_dir = os.path.join(app.user_data_dir, "registered_faces")
        if not os.path.exists(base_dir): os.makedirs(base_dir)
        self.embedder.load_database(base_dir)
        self.ask_permissions()

    def ask_permissions(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            def cb(p, r):
                if all(r): Clock.schedule_once(lambda dt: self.start_system(), 0.1)
            request_permissions([Permission.CAMERA], cb)
        else:
            self.start_system()

    def start_system(self):
        try:
            # 1. Ensure the booth exists
            if not self.booth: 
                self.booth = FaceRegister()
            
            # 2. FORCE FAST MODE EVERY TIME (Moved outside the 'if' block!)
            self.booth.STABILITY_THRESHOLD = 1
            self.booth.COOLDOWN = 0.0
            self.booth.MAX_SHOTS = 999999
            
            # 3. Start the camera
            if not self.cam:
                self.cam = Camera(resolution=(640, 480), play=True, index=0)
                self.cam.opacity = 0
                self.cam.size_hint = (0, 0)
                self.layout.add_widget(self.cam)

            # 4. Start the update loop safely
            Clock.unschedule(self.update)
            self.event = Clock.schedule_interval(self.update, 1.0 / 30.0)
            
        except Exception as e:
            print(f"Recognition Camera Error: {e}")

    def update(self, dt):
        if not self.cam or not self.cam.texture: return

        # 1. Capture current frame
        pixels = self.cam.texture.pixels
        w, h = self.cam.texture.size
        raw_frame = np.frombuffer(pixels, dtype=np.uint8).reshape((h, w, 4))
        ui_frame = cv2.rotate(raw_frame, cv2.ROTATE_90_CLOCKWISE)
        ui_frame = cv2.flip(ui_frame, 1) 
        
        current_time = time.time()

        # 2. Synchronous AI with Interval (No Threading)
        if (current_time - self.last_ai_time > self.ai_interval):
            self.last_ai_time = current_time
            self.run_ai_logic(ui_frame, current_time)

        # 3. Update UI
        self.update_ui_state()
        self.render_frame(ui_frame)

    def run_ai_logic(self, frame, current_time):
        """Runs on the Main Thread but restricted by the interval."""
        try:
            fast_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            fast_frame_bgr = cv2.cvtColor(fast_frame, cv2.COLOR_RGBA2BGR)
            
            result = self.booth.run(fast_frame_bgr)
            face_crop = result.get('captured_face')
            
            if face_crop is not None:
                # Resize directly to the 112x112 size required by MobileFaceNet
                crop_ready = cv2.resize(face_crop, (112, 112))
                
                # Run Recognition!
                name, conf = self.embedder.recognize(crop_ready)
                
                # --- TEMPORAL CONSENSUS TRACKER ---
                if name != "Unknown":
                    # 1. Did the AI guess the same person as last time?
                    if name == self.tracking_name:
                        self.consecutive_matches += 1
                    else:
                        # Reset the counter for a new person
                        self.tracking_name = name
                        self.consecutive_matches = 1

                    # 2. Update UI instantly so it feels fast, but DON'T log yet
                    self.active_user = name
                    self.user_confidence = conf
                    self.persistence_frames = 10 
                    
                    # 3. ONLY log to database if we hit the consecutive threshold!
                    if self.consecutive_matches >= self.REQUIRED_MATCHES:
                        last = self.recently_logged.get(name, 0)
                        if current_time - last > self.log_cooldown:
                            self.embedder.log_recognition(name)
                            self.recently_logged[name] = current_time
                            print(f"VERIFIED: {name} securely logged to DB.")
                else:
                    # If we see 'Unknown', break the streak
                    self.tracking_name = None
                    self.consecutive_matches = 0
                    self.decay_persistence()
            else:
                # If no face is on screen, break the streak
                self.tracking_name = None
                self.consecutive_matches = 0
                self.decay_persistence()

        except Exception as e:
            print(f"AI Sync Error: {e}")

    def decay_persistence(self):
        if self.persistence_frames > 0:
            self.persistence_frames -= 1
        else:
            self.active_user = None

    def update_ui_state(self):
        if self.active_user:
            self.status_label.text = f"Recognized: {self.active_user} ({(self.user_confidence*100):.1f}%)"
            self.status_label.color = (0, 1, 0, 1) if self.active_user != "Unknown User" else (1, 0, 0, 1)
        else:
            self.status_label.text = "Looking for a face..."
            self.status_label.color = (1, 1, 1, 1)

    def render_frame(self, frame):
        h, w, _ = frame.shape
        display = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        buf = cv2.flip(display, 0).tobytes()
        if not self.image_widget.texture or self.image_widget.texture.size != (w, h):
            self.image_widget.texture = Texture.create(size=(w, h), colorfmt='rgb')
        self.image_widget.texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')

    def go_back(self, instance):
        self.cleanup()
        self.manager.current = 'main_menu'

    def on_leave(self):
        self.cleanup()

    def cleanup(self):
        if hasattr(self, 'event'): Clock.unschedule(self.event)
        if self.cam:
            self.cam.play = False
            self.layout.remove_widget(self.cam)
            self.cam = None
        if self.booth: self.booth.reset_session()
        self.image_widget.texture = None