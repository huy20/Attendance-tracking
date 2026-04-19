import os
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.core.window import Window

# Import your registration module
from registration_screen import FaceRegistrationScreen
from RegisteredID import ViewFacesScreen
from recognition_screen import FaceRecognitionScreen
from gallery import UserGalleryScreen
from log_history_screen import LogHistoryScreen
from network_sync import AttendanceSyncer

Window.softinput_mode = 'below_target'

class MainMenuScreen(Screen):
    def __init__(self, **kwargs):
        super(MainMenuScreen, self).__init__(**kwargs)
        # Added spacing so the buttons aren't touching
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        
        # 1. Registration Button
        btn_register = Button(text="Register New Face", size_hint_y=None, height=100)
        btn_register.bind(on_press=self.go_to_registration)
        
        # 2. View Users Button
        btn_view = Button(text="View Registered Faces", size_hint_y=None, height=100)
        btn_view.bind(on_press=self.go_to_view_faces)
        
        btn_recognize = Button(text="Start Live Recognition", size_hint_y=None, height=100)
        btn_recognize.bind(on_press=self.go_to_recognition)
        
        btn_log = Button(text="Attendance List", size_hint_y=None, height=100)
        btn_log.bind(on_press=self.go_to_log_history)
        
        layout.add_widget(btn_register)
        layout.add_widget(btn_view)
        layout.add_widget(btn_recognize)
        layout.add_widget(btn_log)
        self.add_widget(layout)

    def go_to_registration(self, instance):
        self.manager.current = 'register_stage'

    def go_to_view_faces(self, instance):
        self.manager.current = 'view_faces_stage'
    
    def go_to_recognition(self, instance):
        self.manager.current = 'recognition_stage'
        
    def go_to_log_history(self, instance):
        self.manager.current = 'log_screen'
        

class MyMainApp(App):
    def build(self):
        sm = ScreenManager()
        
        # Add all three stages to the ScreenManager
        sm.add_widget(MainMenuScreen(name='main_menu'))
        sm.add_widget(FaceRegistrationScreen(name='register_stage'))
        sm.add_widget(ViewFacesScreen(name='view_faces_stage'))
        sm.add_widget(FaceRecognitionScreen(name='recognition_stage'))
        sm.add_widget(UserGalleryScreen(name='gallery_stage'))
        sm.add_widget(LogHistoryScreen(name='log_screen'))
        return sm
    def on_start(self):
        """This runs automatically right after build() finishes."""
        # 1. Define the exact path to your database folder
        base_dir = os.path.join(self.user_data_dir, "registered_faces")
        
        # 2. Put your Desktop's IP address here
        HOST_URL = "http://192.168.1.33:5000/sync" 
        
        # 3. Create the syncer and attach it to the app so it stays alive
        self.syncer = AttendanceSyncer(base_dir=base_dir, host_url=HOST_URL, sync_interval=60.0)
        
        # 4. Start the background loop!
        self.syncer.start_syncing()

if __name__ == '__main__':
    MyMainApp().run()