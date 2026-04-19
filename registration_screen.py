import os
os.environ['OPENCV_SKIP_BOOTSTRAP_CONFIG'] = '1'

from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
import cv2
import numpy as np
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.camera import Camera
from kivy.clock import Clock, mainthread
from kivy.graphics.texture import Texture
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.utils import platform
import threading
import glob
import time
import sqlite3

from face_register import FaceRegister
from face_recognition import FaceEmbedder

class FaceRegistrationScreen(Screen):
    def __init__(self, **kwargs):
        super(FaceRegistrationScreen, self).__init__(**kwargs)
        
        # --- UI SETUP ---
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        self.image_widget = Image(allow_stretch=True, keep_ratio=True)
        self.progress_bar = ProgressBar(max=1.0, value=0, size_hint_y=None, height=20)
        self.status_label = Label(text="Initializing UI...", size_hint_y=None, height=40)
        self.count_label = Label(text="Shots: 0/0", size_hint_y=None, height=40)

        self.layout.add_widget(self.image_widget)
        self.layout.add_widget(self.progress_bar)
        self.layout.add_widget(self.status_label)
        self.layout.add_widget(self.count_label)
        
        self.add_widget(self.layout)
        
        # --- STATE VARIABLES ---
        self.person_name = "User_001" 
        self.last_saved_count = 0
        self.booth = None
        self.cam = None
        
        self.last_ai_time = 0
        self.ai_interval = 0.2  
        self.latest_result = {"status": "WAITING", "reasons": [], "progress": 0, "count": 0, "max_shots": 50}
        self.embedder = FaceEmbedder("MobileFaceNet.onnx")

    def on_enter(self, *args):
        """Called automatically when the screen is displayed."""
        app = App.get_running_app()
        self.base_dir = os.path.join(app.user_data_dir, "registered_faces")

        # Show the popup first instead of starting the camera immediately
        self.show_user_info_popup()

    def show_user_info_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        content.add_widget(Label(text="Please enter user name or ID:"))
        
        self.name_input = TextInput(hint_text="e.g., John_Doe", multiline=False, size_hint_y=None, height=50)
        content.add_widget(self.name_input)
        
        # --- NEW: Create a horizontal layout for side-by-side buttons ---
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)
        
        cancel_btn = Button(text="Cancel", background_color=(0.8, 0.2, 0.2, 1)) # Red color
        cancel_btn.bind(on_release=self.cancel_registration)
        btn_layout.add_widget(cancel_btn)
        
        start_btn = Button(text="Start Registration", background_color=(0.2, 0.6, 0.2, 1)) # Green color
        start_btn.bind(on_release=self.start_after_popup)
        btn_layout.add_widget(start_btn)
        
        content.add_widget(btn_layout)
        # ----------------------------------------------------------------
        
        self.popup = Popup(title="User Information", content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
        self.popup.open()

    def cancel_registration(self, instance):
        """Closes the popup and returns to the Main Menu."""
        self.popup.dismiss()
        # Ensure 'main_menu' matches the exact name you used in your ScreenManager!
        self.manager.current = 'main_menu'

    def start_after_popup(self, instance):
        user_text = self.name_input.text.strip()
        
        # Don't let them proceed if they left it blank
        if not user_text:
            self.name_input.hint_text = "Name cannot be empty!"
            return 
        
        # Safely format the name for folder usage (replace spaces with underscores)
        self.person_name = user_text.replace(" ", "_") 
        self.person_dir = os.path.join(self.base_dir, self.person_name)
        
        if not os.path.exists(self.person_dir):
            os.makedirs(self.person_dir)
            
        self.popup.dismiss()
        
        # Now we proceed with the camera!
        self.ask_permissions()
    
    def on_leave(self, *args):
        """Called automatically when navigating away from the screen."""
        if hasattr(self, 'event'):
            self.event.cancel()
            del self.event
        if self.cam: 
            self.cam.play = False
            # Optional: remove the camera widget to free up memory when leaving
            self.layout.remove_widget(self.cam)
            self.cam = None

    def ask_permissions(self):
        self.status_label.text = "Asking permission..."
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            def permissions_callback(permissions, results):
                if all(results):
                    self.status_label.text = "Permission granted!"
                    Clock.schedule_once(lambda dt: self.start_system(), 0.1)
                else:
                    self.status_label.text = "Error: Camera permission denied"
            request_permissions([Permission.CAMERA], permissions_callback)
        else:
            self.start_system()

    def start_system(self):
        self.status_label.text = "Starting Native Camera..."
        
        try:
            # 1. Always create the booth FIRST to prevent crashes
            if not self.booth:
                self.booth = FaceRegister()

            # 2. Attach the strict parameters directly to the BOOTH, not the screen
            self.booth.COOLDOWN = 0.2
            self.booth.MAX_SHOTS = 10
            self.booth.STABILITY_THRESHOLD = 20
            
            # 3. Now that the booth exists and is configured, it is safe to reset
            self.booth.reset_session()

            # 4. Start the camera
            if not self.cam:
                self.cam = Camera(resolution=(640, 480), play=True, index=0)
                self.cam.opacity = 0
                self.cam.size_hint = (0, 0)
                self.layout.add_widget(self.cam)

            if not hasattr(self, 'event'):
                self.event = Clock.schedule_interval(self.update, 1.0 / 30.0)
                
        except Exception as e:
            self.status_label.text = f"Camera Error: {str(e)}"

    def start_embedding_process(self):
        if hasattr(self, 'event'):
            self.event.cancel()
        if self.cam:
            self.cam.play = False
            
        self.status_label.text = "Status: Generating AI Embeddings... Please wait."
        self.progress_bar.value = 0 
        
        thread = threading.Thread(target=self._background_embedding_task)
        thread.daemon = True 
        thread.start()

    def _background_embedding_task(self):
        # 1. Setup SQLite Database in your safe app storage folder
        db_path = os.path.join(self.base_dir, "faces.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create the table if it doesn't exist yet
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_name TEXT,
                embedding BLOB
            )
        ''')
        conn.commit()

        # 2. Process all images
        image_paths = glob.glob(os.path.join(self.person_dir, "*.jpg"))
        all_embeddings = []
        total_images = len(image_paths)

        if total_images == 0:
            print("ERROR: No images found to process!")
            self.on_embeddings_finished()
            return

        for i, img_path in enumerate(image_paths):
            cropped_face = cv2.imread(img_path)
            vector = self.embedder.get_embedding(cropped_face)
            all_embeddings.append(vector)
            
            # Update progress bar
            progress = (i + 1) / total_images
            self.update_embedding_progress(progress)

        # 3. Chunk into groups of 5 and Average
        chunk_size = 5
        saved_chunks = 0
        
        for i in range(0, len(all_embeddings), chunk_size):
            chunk = all_embeddings[i : i + chunk_size]
            
            if len(chunk) > 0:
                # Average the 5 embeddings together
                chunk_array = np.array(chunk)
                average_embedding = np.mean(chunk_array, axis=0)
                
                # Convert the NumPy array to raw bytes for the database
                # Force float32 to ensure consistency when reading it back later
                emb_bytes = average_embedding.astype(np.float32).tobytes()
                
                # Insert into Database
                cursor.execute(
                    "INSERT INTO user_embeddings (person_name, embedding) VALUES (?, ?)", 
                    (self.person_name, emb_bytes)
                )
                saved_chunks += 1

        # 4. Save and close database
        conn.commit()
        conn.close()
        
        print(f"SUCCESS: Saved {saved_chunks} averaged embeddings for {self.person_name} into database.")

        # 5. Tell Kivy the thread is done
        self.on_embeddings_finished()

    @mainthread
    def update_embedding_progress(self, progress):
        self.progress_bar.value = progress

    @mainthread
    def on_embeddings_finished(self):
        self.status_label.text = "Status: Registration Complete! Profile Saved."
        self.progress_bar.value = 1.0
        Clock.schedule_once(self.go_to_main_screen, 3.0)

    def go_to_main_screen(self, dt):
        """Resets the UI and switches back to the main menu."""
        # 1. Clean up processing locks and counts
        if hasattr(self, 'is_processing'):
            del self.is_processing
        self.last_saved_count = 0
        if self.booth:
            self.booth.reset_session()
            
        # 2. Reset UI for the next time they visit this screen
        self.progress_bar.value = 0
        self.count_label.text = "Shots: 0/50"
        self.status_label.text = "Initializing UI..."
        
        # 3. Stop the camera
        if self.cam:
            self.cam.play = False
            
        # 4. Switch screens! 
        # (Make sure to replace 'main_screen' with the exact name you gave your main screen)
        if self.manager:
            self.manager.current = 'main_menu'
    
    def update(self, dt):
        if not self.cam or not self.cam.texture or not self.booth: 
            return

        pixels = self.cam.texture.pixels
        w, h = self.cam.texture.size
        raw_frame = np.frombuffer(pixels, dtype=np.uint8).reshape((h, w, 4))
        
        ui_frame = cv2.rotate(raw_frame, cv2.ROTATE_90_CLOCKWISE)
        ui_frame = cv2.flip(ui_frame, 1) 

        current_time = time.time()
        if current_time - self.last_ai_time >= self.ai_interval:
            self.last_ai_time = current_time
            
            fast_frame = cv2.resize(ui_frame, (0, 0), fx=0.5, fy=0.5)
            frame_bgr = cv2.cvtColor(fast_frame, cv2.COLOR_RGBA2BGR)
            
            try:
                self.latest_result = self.booth.run(frame_bgr)
            except Exception as e:
                print(f"AI Update Error: {e}")

        result = self.latest_result
        reason_text = f" ({result['reasons'][0]})" if result.get('reasons') else ""
        self.status_label.text = f"Status: {result['status']}{reason_text}"
        self.count_label.text = f"Shots: {result.get('count', 0)}/{result.get('max_shots', 50)}"
        self.progress_bar.value = result.get('progress', 0)

        current_count = result.get('count', 0)
        
        if current_count > self.last_saved_count:
            timestamp = int(time.time() * 1000)
            filename = os.path.join(self.person_dir, f"face_{current_count}_{timestamp}.jpg")
            
            # THE FIX: No more coordinate math! 
            # captured_face is ALREADY the perfectly cropped and padded BGR image array.
            save_frame = result['captured_face']
            
            # Just save it directly to the folder!
            cv2.imwrite(filename, save_frame)
            
            self.last_saved_count = current_count
            print(f"Successfully saved to: {filename}")

        max_shots = result.get('max_shots', 50)
        if current_count >= max_shots and not hasattr(self, 'is_processing'):
            self.is_processing = True 
            self.start_embedding_process()
            return 
        
        new_h, new_w, _ = ui_frame.shape 
        display_frame = cv2.cvtColor(ui_frame, cv2.COLOR_RGBA2RGB)
        buf = cv2.flip(display_frame, 0).tobytes() 
        
        if self.image_widget.texture is None or self.image_widget.texture.size != (new_w, new_h):
            self.image_widget.texture = Texture.create(size=(new_w, new_h), colorfmt='rgb')
            
        self.image_widget.texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
        self.image_widget.canvas.ask_update()