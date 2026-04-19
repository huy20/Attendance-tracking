import os
import sqlite3
import csv
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button

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
        self.scroll = ScrollView(size_hint=(1, 0.75))
        # GridLayout to hold columns (e.g., Name, Time)
        self.grid = GridLayout(cols=2, spacing=5, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        self.layout.add_widget(self.scroll)
        
        # 3. Footer Action Buttons
        self.footer = BoxLayout(orientation='horizontal', size_hint_y=0.15, spacing=10)
        
        self.btn_export = Button(text="Export to CSV", background_color=(0, 0.7, 0, 1))
        self.btn_export.bind(on_press=self.export_csv)
        self.footer.add_widget(self.btn_export)
        
        self.btn_back = Button(text="Back to Main Menu", background_color=(0.7, 0, 0, 1))
        self.btn_back.bind(on_press=self.go_back)
        self.footer.add_widget(self.btn_back)
        
        self.layout.add_widget(self.footer)
        self.add_widget(self.layout)

    def on_enter(self):
        """Kivy calls this automatically every time the screen is shown!"""
        self.load_todays_logs()

    def load_todays_logs(self):
        """Reads attendance.db and populates the scrollable grid."""
        self.grid.clear_widgets() # Clear old data
        
        # Add Column Headers
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
            
            # Get today's date string (e.g., '2026-04-19')
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # NOTE: Change 'attendance_table' to your actual table name!
            # We use LIKE to filter only timestamps that start with today's date.
            cursor.execute(f"SELECT person_name, timestamp FROM attendance_logs WHERE timestamp LIKE '{today_str}%' ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            
            self.header_label.text = f"Today's Attendance ({len(rows)} records)"
            
            for row in rows:
                name, timestamp = row
                self.grid.add_widget(Label(text=str(name), size_hint_y=None, height=40))
                # Only show the time (HH:MM:SS) to save space on mobile
                time_only = timestamp.split(" ")[1] if " " in timestamp else timestamp
                self.grid.add_widget(Label(text=str(time_only), size_hint_y=None, height=40))
                
            conn.close()
            
        except Exception as e:
            print(f"DB Load Error: {e}")
            self.header_label.text = "Error loading logs"

    def export_csv(self, instance):
        """Exports the entire database or today's logs to a CSV file."""
        try:
            app = App.get_running_app()
            base_dir = os.path.join(app.user_data_dir, "registered_faces")
            db_path = os.path.join(base_dir, 'attendance.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Fetch EVERYTHING for the export (you can add the WHERE clause if you only want today's)
            cursor.execute("SELECT * FROM attendance_logs ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            
            # Extract column headers dynamically
            column_names = [description[0] for description in cursor.description]
            
            # Create a file name with exact date and time
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
            csv_filename = f"Attendance_{current_time}.csv"
            csv_path = os.path.join(app.user_data_dir, csv_filename)
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(column_names)
                writer.writerows(rows)
                
            conn.close()
            
            # Flash success message on the UI
            self.btn_export.text = f"Exported: {csv_filename}!"
            
        except Exception as e:
            print(f"Export Error: {e}")
            self.btn_export.text = "Export Failed"

    def go_back(self, instance):
        # Reset export button text if it was changed
        self.btn_export.text = "Export to CSV"
        # Switch back to your camera screen (Make sure the name matches your ScreenManager!)
        self.manager.current = 'main_menu'