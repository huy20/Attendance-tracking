from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, RoundedRectangle, Rectangle

class RoundedButton(Button):
    def __init__(self, **kwargs):
        self.bg_color = kwargs.pop('bg_color', get_color_from_hex("#1E88E5"))
        self.radius = kwargs.pop('radius', [18,])
        super(RoundedButton, self).__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.font_size = '20sp'
        self.bold = True
        self.color = (1, 1, 1, 1)
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class Card(BoxLayout):
    """A rounded card widget for wrapping content."""
    def __init__(self, **kwargs):
        self.bg_color = kwargs.pop('bg_color', get_color_from_hex("#1C2333"))
        self.radius = kwargs.pop('radius', [16,])
        super(Card, self).__init__(**kwargs)
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


def make_screen_bg(widget):
    """Attach a dark background to any Screen widget."""
    from kivy.graphics import Color, Rectangle
    with widget.canvas.before:
        Color(*get_color_from_hex("#0D1117"))
        bg = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda *a: setattr(bg, 'pos', widget.pos),
                size=lambda *a: setattr(bg, 'size', widget.size))


def header_label(text, font_size='28sp'):
    return Label(
        text=text,
        font_size=font_size,
        bold=True,
        color=get_color_from_hex("#E6EDF3"),
        size_hint_y=None,
        height=56,
        halign='left',
        valign='middle',
    )


def sub_label(text, font_size='16sp', color="#8B949E"):
    return Label(
        text=text,
        font_size=font_size,
        color=get_color_from_hex(color),
        size_hint_y=None,
        height=30,
        halign='left',
        valign='middle',
    )
