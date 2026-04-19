import os
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

class ViewFacesScreen(Screen):
    def __init__(self, **kwargs):
        super(ViewFacesScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        # Title
        title = Label(text="Registered Users", size_hint_y=None, height=50, font_size=24)
        self.layout.add_widget(title)

        # Scrollable area setup
        self.scroll = ScrollView(size_hint=(1, 1))
        self.list_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        self.scroll.add_widget(self.list_layout)

        self.layout.add_widget(self.scroll)

        # Back button to return to main menu
        btn_back = Button(text="Back to Menu", size_hint_y=None, height=60)
        btn_back.bind(on_release=self.go_back)
        self.layout.add_widget(btn_back)

        self.add_widget(self.layout)

    def on_enter(self, *args):
        # Clear the old list
        self.list_layout.clear_widgets()

        app = App.get_running_app()
        base_dir = os.path.join(app.user_data_dir, "registered_faces")

        # Check if the folder exists and populate the list
        if os.path.exists(base_dir):
            users = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
            
            if users:
                for user in users:
                    display_name = user.replace("_", " ")
                    btn = Button(text=display_name, size_hint_y=None, height=50)
                    
                    # --- THE FIX ---
                    # Bind the button to our new method, passing the specific folder name
                    btn.bind(on_release=lambda instance, u=user: self.open_user_gallery(u))
                    
                    self.list_layout.add_widget(btn)
            else:
                self.list_layout.add_widget(Label(text="No users registered yet.", size_hint_y=None, height=50))
        else:
            self.list_layout.add_widget(Label(text="No users registered yet.", size_hint_y=None, height=50))

    def open_user_gallery(self, username):
        """Passes the username to the Gallery Screen and switches to it."""
        # Grab the gallery screen from the ScreenManager
        gallery_screen = self.manager.get_screen('gallery_stage')
        
        # Tell the gallery screen whose pictures to load
        gallery_screen.target_user = username
        
        # Switch the screen
        self.manager.current = 'gallery_stage'

    def go_back(self, instance):
        self.manager.current = 'main_menu'