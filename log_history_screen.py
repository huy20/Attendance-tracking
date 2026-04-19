import os
import sqlite3
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

class LogHistoryScreen(Screen):
    def __init__(self, **kwargs):
        super(LogHistoryScreen, self).__init__(**kwargs)
        
        # Main layout
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # 1. Header Area
        self.header_label = Label(
            text="Today's Attendance", 
            font_size='24sp', 
            bold=True, 
            size_hint_y=0.1
        )
        self.layout.add_widget(self.header_label)
        
        # 2. Scrollable Data Grid
        self.scroll = ScrollView(size_hint=(1, 0.6))
        self.grid = GridLayout(cols=2, spacing=5, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        self.layout.add_widget(self.scroll)
        
        # 3. NEW: Network Controls Area
        self.net_layout = BoxLayout(orientation='horizontal', size_hint_y=0.15, spacing=10)
        
        self.ip_input = TextInput(
            hint_text="Host IP (e.g. 192.168.1.15)", 
            multiline=False, 
            size_hint_x=0.6,
            font_size='18sp'
        )
        self.net_layout.add_widget(self.ip_input)
        
        self.btn_toggle_sync = Button(text="Auto-Sync: ON", background_color=(0, 0.5, 0.8, 1), size_hint_x=0.4)
        self.btn_toggle_sync.bind(on_press=self.toggle_auto_sync)
        self.net_layout.add_widget(self.btn_toggle_sync)
        
        self.layout.add_widget(self.net_layout)
        
        # 4. Footer Action Buttons
        self.footer = BoxLayout(orientation='horizontal', size_hint_y=0.15, spacing=10)
        
        self.btn_sync = Button(text="Manual Sync Now", background_color=(0, 0.7, 0, 1))
        self.btn_sync.bind(on_press=self.manual_sync)
        self.footer.add_widget(self.btn_sync)
        
        self.btn_back = Button(text="Back to Main Menu", background_color=(0.7, 0, 0, 1))
        self.btn_back.bind(on_press=self.go_back)
        self.footer.add_widget(self.btn_back)
        
        self.layout.add_widget(self.footer)
        self.add_widget(self.layout)

    def on_enter(self):
        self.load_todays_logs()
        self.sync_ui_with_app_state()

    def sync_ui_with_app_state(self):
        """Updates the buttons to match the Syncer's current state when entering the screen."""
        app = App.get_running_app()
        if hasattr(app, 'syncer'):
            # If the syncer has an active event, it is currently ON
            if app.syncer.event:
                self.btn_toggle_sync.text = "Auto-Sync: ON"
                self.btn_toggle_sync.background_color = (0, 0.5, 0.8, 1) # Blue
            else:
                self.btn_toggle_sync.text = "Auto-Sync: OFF"
                self.btn_toggle_sync.background_color = (0.5, 0.5, 0.5, 1) # Gray

    def load_todays_logs(self):
        """Reads attendance.db and populates the scrollable grid."""
        self.grid.clear_widgets() 
        
        self.grid.add_widget(Label(text="Name", bold=True, size_hint_y=None, height=40))
        self.grid.add_widget(Label(text="Timestamp", bold=True, size_hint_y=None, height=40))
        
        try:
            app = App.get_running_app()
            base_dir = os.path.join(app.user_data_dir, "registered_faces")
            db_path = os.path.join(base_dir, 'attendance.db')
            
            if not os.path.exists(db_path):
                self.header_label.text = "No Database Found"
                return
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute(f"SELECT person_name, timestamp FROM attendance_logs WHERE timestamp LIKE '{today_str}%' ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            
            self.header_label.text = f"Today's Attendance ({len(rows)} records)"
            
            for row in rows:
                name, timestamp = row
                self.grid.add_widget(Label(text=str(name), size_hint_y=None, height=40))
                time_only = timestamp.split(" ")[1] if " " in timestamp else timestamp
                self.grid.add_widget(Label(text=str(time_only), size_hint_y=None, height=40))
                
            conn.close()
            
        except Exception as e:
            print(f"DB Load Error: {e}")
            self.header_label.text = "Error loading logs"

    def get_formatted_url(self):
        """Helper function to turn an IP address into a proper Flask URL"""
        ip = self.ip_input.text.strip()
        if not ip:
            return None
        # If the user just typed "192.168.1.15", automatically format it!
        if "http" not in ip:
            return f"http://{ip}:5000/sync"
        return ip

    def update_syncer_url(self):
        app = App.get_running_app()
        url = self.get_formatted_url()
        if url and hasattr(app, 'syncer'):
            app.syncer.host_url = url
            return True
        return False

    def manual_sync(self, instance):
        """Triggers a sync immediately, regardless of the timer."""
        if not self.update_syncer_url():
            self.btn_sync.text = "Enter IP first!"
            return

        app = App.get_running_app()
        app.syncer.sync_with_host(0) # Pass 0 because 'dt' is normally passed by Clock
        self.btn_sync.text = "Sync Triggered!"

    def toggle_auto_sync(self, instance):
        """Turns the background syncing on or off."""
        app = App.get_running_app()
        if not hasattr(app, 'syncer'): return
        
        # Always update URL before toggling, in case they changed it
        self.update_syncer_url()

        if app.syncer.event:
            # It's currently ON, so turn it OFF
            app.syncer.stop_syncing()
            self.btn_toggle_sync.text = "Auto-Sync: OFF"
            self.btn_toggle_sync.background_color = (0.5, 0.5, 0.5, 1) # Gray out the button
        else:
            # It's currently OFF, so turn it ON
            if not self.ip_input.text.strip():
                self.btn_toggle_sync.text = "Need IP!"
                return
            app.syncer.start_syncing()
            self.btn_toggle_sync.text = "Auto-Sync: ON"
            self.btn_toggle_sync.background_color = (0, 0.5, 0.8, 1) # Return to Blue

    def go_back(self, instance):
        self.btn_sync.text = "Manual Sync Now"
        if self.btn_toggle_sync.text == "Need IP!":
            self.sync_ui_with_app_state() # Reset button UI
        self.manager.current = 'main_menu'