#!/usr/bin/env python3
import math
import cairo
from gi.repository import Gtk, Gsk

class CustomImage(Gtk.Widget):
    def __init__(self, image_path: str, border_radius: float = 0):
        super().__init__()
        self._border_radius = border_radius
        # Load the image as a Cairo image surface.
        self._surface = cairo.ImageSurface.create_from_png(image_path)
        # Set the widget's initial size to the image's natural size.
        self.set_size_request(self._surface.get_width(), self._surface.get_height())

    def snapshot(self, snapshot: Gtk.Snapshot) -> None:
        # Get the current widget dimensions.
        width = self.get_width()
        height = self.get_height()

        # Create a rounded rectangle clip region.
        clip = Gsk.RoundedRect.new(0, 0, width, height, self._border_radius)
        snapshot.push_clip(clip)

        # Append custom drawing via a Cairo callback.
        snapshot.append_cairo(self._draw_image)
        snapshot.pop()

    def _draw_image(self, cr: cairo.Context) -> None:
        # Get widget dimensions.
        width = self.get_width()
        height = self.get_height()

        # Get the image's natural dimensions.
        img_width = self._surface.get_width()
        img_height = self._surface.get_height()

        # Scale the Cairo context so that the image fills the widget.
        scale_x = width / img_width
        scale_y = height / img_height
        cr.scale(scale_x, scale_y)

        # Draw the image onto the context.
        cr.set_source_surface(self._surface, 0, 0)
        cr.paint()

class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.example.roundimage")

    def do_activate(self):
        # Create an application window.
        win = Gtk.ApplicationWindow(application=self, title="Custom Image with Rounded Corners")
        # Replace 'path/to/your/image.png' with your actual image path.
        custom_image = CustomImage("/home/gunit/.config/Ax-Shell/assets/ax.png", border_radius=20)
        win.set_child(custom_image)
        win.present()

if __name__ == '__main__':
    app = MyApp()
    app.run()
