import os
import shutil
import sqlite3
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup

class ViewFacesScreen(Screen):
    def __init__(self, **kwargs):
        super(ViewFacesScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        # Title
        self.title_label = Label(text="Registered Users", size_hint_y=None, height=50, font_size=24)
        self.layout.add_widget(self.title_label)

        # Scrollable area setup
        self.scroll = ScrollView(size_hint=(1, 1))
        self.list_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        self.scroll.add_widget(self.list_layout)

        self.layout.add_widget(self.scroll)

        # Back button to return to main menu
        btn_back = Button(text="Back to Menu", size_hint_y=None, height=60, background_color=(0.5, 0.5, 0.5, 1))
        btn_back.bind(on_release=self.go_back)
        self.layout.add_widget(btn_back)

        self.add_widget(self.layout)

    def on_enter(self, *args):
        # Refresh the list every time we open the screen
        self.load_users()

    def load_users(self):
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
                    
                    # Create a horizontal row for each user
                    row = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
                    
                    # The user's name
                    lbl = Label(text=display_name, size_hint_x=0.7, font_size='18sp')
                    
                    # The delete button - now triggers the confirmation popup!
                    btn_del = Button(text="Delete", background_color=(0.8, 0.2, 0.2, 1), size_hint_x=0.3)
                    btn_del.bind(on_release=lambda instance, u=user: self.confirm_delete_popup(u))
                    
                    row.add_widget(lbl)
                    row.add_widget(btn_del)
                    
                    self.list_layout.add_widget(row)
            else:
                self.list_layout.add_widget(Label(text="No users registered yet.", size_hint_y=None, height=50))
        else:
            self.list_layout.add_widget(Label(text="No users registered yet.", size_hint_y=None, height=50))

    def confirm_delete_popup(self, user_folder):
        """Displays a confirmation popup before deleting a user."""
        display_name = user_folder.replace("_", " ")
        
        # Create the content layout for the popup
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        message = Label(text=f"Are you sure you want to delete\n{display_name}?\nThis cannot be undone.", 
                        halign="center", font_size='16sp')
        content.add_widget(message)
        
        # Horizontal layout for the Yes/No buttons
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)
        
        btn_yes = Button(text="Yes, Delete", background_color=(0.8, 0.2, 0.2, 1))
        btn_no = Button(text="Cancel", background_color=(0.5, 0.5, 0.5, 1))
        
        btn_layout.add_widget(btn_yes)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        
        # Create the popup
        popup = Popup(title="Confirm Deletion", content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
        
        # Bind the buttons
        btn_no.bind(on_release=popup.dismiss)
        
        # When "Yes" is clicked, call the actual delete function and dismiss the popup
        def on_confirm_delete(instance):
            self.execute_delete_user(user_folder)
            popup.dismiss()
            
        btn_yes.bind(on_release=on_confirm_delete)
        
        popup.open()

    def execute_delete_user(self, user_folder):
        """Actually handles the physical deletion of data."""
        app = App.get_running_app()
        base_dir = os.path.join(app.user_data_dir, "registered_faces")
        user_dir = os.path.join(base_dir, user_folder)
        db_path = os.path.join(base_dir, "faces.db")

        # 1. Delete the Embeddings from the Database
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_embeddings WHERE person_name = ?", (user_folder,))
                rows_deleted = cursor.rowcount
                conn.commit()
                conn.close()
                print(f"Deleted {rows_deleted} face embedding(s) for {user_folder}.")
            except Exception as e:
                print(f"Database Deletion Error for {user_folder}: {e}")

        # 2. Delete the Physical Image Folder
        if os.path.exists(user_dir):
            try:
                shutil.rmtree(user_dir)
                print(f"Deleted physical image folder: {user_folder}")
            except Exception as e:
                print(f"Error deleting folder {user_folder}: {e}")

        # 3. Immediately refresh the UI so the user disappears from the screen
        self.load_users()

    def go_back(self, instance):
        self.manager.current = 'main_menu'