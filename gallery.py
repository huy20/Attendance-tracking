import os
import glob
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.core.window import Window

class UserGalleryScreen(Screen):
    def __init__(self, **kwargs):
        super(UserGalleryScreen, self).__init__(**kwargs)
        
        # This will be updated by ViewFacesScreen before we switch to this screen
        self.target_user = None 
        
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        self.header_label = Label(text="Loading images...", size_hint_y=None, height=50, font_size=24)
        self.layout.add_widget(self.header_label)
        
        self.scroll = ScrollView(size_hint=(1, 1))
        self.grid = GridLayout(cols=3, spacing=10, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        
        self.layout.add_widget(self.scroll)
        
        btn_back = Button(text="Back to User List", size_hint_y=None, height=60)
        btn_back.bind(on_release=self.go_back)
        self.layout.add_widget(btn_back)
        
        self.add_widget(self.layout)

    def on_enter(self, *args):
        self.grid.clear_widgets()
        
        # Safety check just in case it was opened without a target user
        if not self.target_user:
            self.header_label.text = "Error: No user selected."
            return

        app = App.get_running_app()
        user_dir = os.path.join(app.user_data_dir, "registered_faces", self.target_user)
        
        display_name = self.target_user.replace("_", " ")
        
        if not os.path.exists(user_dir):
            self.header_label.text = f"No folder found for {display_name}"
            return

        image_paths = glob.glob(os.path.join(user_dir, "*.jpg"))
        
        if not image_paths:
            self.header_label.text = f"No images found for {display_name}"
            return
            
        self.header_label.text = f"Images for {display_name} ({len(image_paths)})"

        for img_path in image_paths:
            img_widget = Image(
                source=img_path,
                allow_stretch=True,
                keep_ratio=True,
                size_hint_y=None,
                height=Window.width / 3 
            )
            self.grid.add_widget(img_widget)

    def on_leave(self, *args):
        # Clear out the images from memory when we leave the screen
        self.grid.clear_widgets()

    def go_back(self, instance):
        # Go back to the list of users instead of the main menu
        self.manager.current = 'view_faces_stage'