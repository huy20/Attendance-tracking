import os
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle, RoundedRectangle

from ui_components import RoundedButton, Card, make_screen_bg

from registration_screen import FaceRegistrationScreen
from RegisteredID import ViewFacesScreen
from recognition_screen import FaceRecognitionScreen
from log_history_screen import LogHistoryScreen
from gallery import UserGalleryScreen

Window.softinput_mode = 'below_target'


class MenuButton(RoundedButton):
    """Large full-width menu button."""
    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', 80)
        kwargs.setdefault('radius', [20,])
        kwargs.setdefault('font_size', '20sp')
        super().__init__(**kwargs)
        self.halign = 'left'
        self.padding_x = 30


class MainMenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        make_screen_bg(self)

        root = BoxLayout(orientation='vertical', padding=[30, 50, 30, 30], spacing=0)

        # ── Hero header ──────────────────────────────────────────────────────
        hero = BoxLayout(orientation='vertical', size_hint_y=None, height=130, spacing=4)

        badge = Label(
            text='SECURE ATTENDANCE',
            font_size='11sp',
            bold=True,
            color=get_color_from_hex("#58A6FF"),
            size_hint_y=None,
            height=22,
        )
        title = Label(
            text='Face Booth',
            font_size='40sp',
            bold=True,
            color=get_color_from_hex("#E6EDF3"),
            size_hint_y=None,
            height=60,
        )
        subtitle = Label(
            text='Powered by MobileFaceNet + RSA Sync',
            font_size='14sp',
            color=get_color_from_hex("#8B949E"),
            size_hint_y=None,
            height=26,
        )
        hero.add_widget(badge)
        hero.add_widget(title)
        hero.add_widget(subtitle)
        root.add_widget(hero)

        # ── Divider ──────────────────────────────────────────────────────────
        divider = BoxLayout(size_hint_y=None, height=1)
        with divider.canvas:
            Color(*get_color_from_hex("#21262D"))
            rect = Rectangle(pos=divider.pos, size=divider.size)
        divider.bind(pos=lambda w, v: setattr(rect, 'pos', v),
                     size=lambda w, v: setattr(rect, 'size', v))
        root.add_widget(divider)

        root.add_widget(BoxLayout(size_hint_y=None, height=30))  # spacer

        # ── Menu buttons ─────────────────────────────────────────────────────
        buttons = BoxLayout(orientation='vertical', spacing=16)

        btn_register = MenuButton(
            text='Register New Face',
            bg_color=get_color_from_hex("#1F6FEB"),
        )
        btn_register.bind(on_press=lambda x: setattr(self.manager, 'current', 'register_stage'))

        btn_view = MenuButton(
            text='View Registered Faces',
            bg_color=get_color_from_hex("#1B4332"),
        )
        btn_view.bind(on_press=lambda x: setattr(self.manager, 'current', 'view_faces_stage'))

        btn_recognize = MenuButton(
            text='Start Live Recognition',
            bg_color=get_color_from_hex("#6E40C9"),
        )
        btn_recognize.bind(on_press=lambda x: setattr(self.manager, 'current', 'recognition_stage'))

        btn_log = MenuButton(
            text='Attendance & Gateway',
            bg_color=get_color_from_hex("#B08800"),
        )
        btn_log.bind(on_press=lambda x: setattr(self.manager, 'current', 'log_screen'))

        for btn in [btn_register, btn_view, btn_recognize, btn_log]:
            buttons.add_widget(btn)

        root.add_widget(buttons)

        # ── Footer ───────────────────────────────────────────────────────────
        root.add_widget(BoxLayout(size_hint_y=1))  # flex spacer
        footer = Label(
            text='android_device_1  •  Tap a button to begin',
            font_size='12sp',
            color=get_color_from_hex("#484F58"),
            size_hint_y=None,
            height=30,
        )
        root.add_widget(footer)
        self.add_widget(root)


class MyMainApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainMenuScreen(name='main_menu'))
        sm.add_widget(FaceRegistrationScreen(name='register_stage'))
        sm.add_widget(ViewFacesScreen(name='view_faces_stage'))
        sm.add_widget(UserGalleryScreen(name='user_gallery'))
        sm.add_widget(FaceRecognitionScreen(name='recognition_stage'))
        sm.add_widget(LogHistoryScreen(name='log_screen'))
        self.syncer = None
        self._sleep_timer = None
        self._timeout = 120
        Window.bind(on_touch_down=self._on_touch)
        self._reset_timer()
        return sm

    def _on_touch(self, win, touch):
        self._reset_timer()

    def _reset_timer(self, *args):
        if self._sleep_timer:
            self._sleep_timer.cancel()
        self._sleep_timer = Clock.schedule_once(self._go_to_sleep, self._timeout)

    def _go_to_sleep(self, dt):
        if self.root.current != 'recognition_stage':
            self.root.current = 'recognition_stage'
        scr = self.root.get_screen('recognition_stage')
        if hasattr(scr, 'enter_sleep_mode'):
            scr.enter_sleep_mode()


if __name__ == '__main__':
    MyMainApp().run()