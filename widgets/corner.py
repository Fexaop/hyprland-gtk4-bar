import gi
import cairo
from enum import Enum
from typing import Literal, Union, Iterable

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

# Define the CornerOrientation enum.
class CornerOrientation(Enum):
    TOP_LEFT = 1
    TOP_RIGHT = 2
    BOTTOM_LEFT = 3
    BOTTOM_RIGHT = 4

# Helper to map a string to the corresponding enum member.
def get_enum_member(enum, value: Union[str, Enum]):
    if isinstance(value, enum):
        return value
    mapping = {
        "top-left": enum.TOP_LEFT,
        "top-right": enum.TOP_RIGHT,
        "bottom-left": enum.BOTTOM_LEFT,
        "bottom-right": enum.BOTTOM_RIGHT,
    }
    return mapping[value.lower()]

# The GTK4 Corner widget.
class Corner(Gtk.DrawingArea):
    def __init__(
        self,
        orientation: Union[
            Literal["top-left", "top-right", "bottom-left", "bottom-right"],
            CornerOrientation,
        ] = CornerOrientation.TOP_RIGHT,
        name: str | None = None,
        visible: bool = True,
        all_visible: bool = False,
        style: str | None = None,
        style_classes: Union[Iterable[str], str, None] = None,
        tooltip_text: str | None = None,
        tooltip_markup: str | None = None,
        h_align: Union[
            Literal["fill", "start", "end", "center", "baseline"], Gtk.Align, None
        ] = None,
        v_align: Union[
            Literal["fill", "start", "end", "center", "baseline"], Gtk.Align, None
        ] = None,
        h_expand: bool = False,
        v_expand: bool = False,
        size: Union[Iterable[int], int, None] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        # Set widget name if provided.
        if name:
            self.set_widget_name(name)
        # Initialize orientation.
        self._orientation = get_enum_member(CornerOrientation, orientation)
        # In GTK4, use set_draw_func() instead of the "draw" signal.
        self.set_draw_func(self.on_draw)

    @property
    def orientation(self) -> CornerOrientation:
        return self._orientation

    @orientation.setter
    def orientation(
        self,
        value: Union[
            Literal["top-left", "top-right", "bottom-left", "bottom-right"],
            CornerOrientation,
        ],
    ):
        self._orientation = get_enum_member(CornerOrientation, value)
        self.queue_draw()

    @staticmethod
    def render_shape(
        cr: cairo.Context, width: float, height: float, orientation: CornerOrientation = CornerOrientation.TOP_LEFT
    ):
        cr.save()
        # Reproduce the original path based on orientation.
        if orientation == CornerOrientation.TOP_LEFT:
            cr.move_to(0, height)
            cr.line_to(0, 0)
            cr.line_to(width, 0)
            cr.curve_to(0, 0, 0, height, 0, height)
        elif orientation == CornerOrientation.TOP_RIGHT:
            cr.move_to(width, height)
            cr.line_to(width, 0)
            cr.line_to(0, 0)
            cr.curve_to(width, 0, width, height, width, height)
        elif orientation == CornerOrientation.BOTTOM_LEFT:
            cr.move_to(0, 0)
            cr.line_to(0, height)
            cr.line_to(width, height)
            cr.curve_to(0, height, 0, 0, 0, 0)
        elif orientation == CornerOrientation.BOTTOM_RIGHT:
            cr.move_to(width, 0)
            cr.line_to(width, height)
            cr.line_to(0, height)
            cr.curve_to(width, height, width, 0, width, 0)
        cr.close_path()
        cr.restore()
    def on_draw(self, drawing_area, cr: cairo.Context, width: int, height: int):
        cr.save()
        # Render the shape and clip the drawing region to it.
        self.render_shape(cr, width, height, self._orientation)
        cr.clip()
    
        # Fill the clipped region with black.
        cr.set_source_rgb(0, 0, 0)  # Black color
        cr.rectangle(0, 0, width, height)
        cr.fill()
    
        cr.restore()
    
