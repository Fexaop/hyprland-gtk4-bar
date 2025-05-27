import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk, Pango
import os
from service.notification import Notifications, Notification

class NotificationStack(Gtk.Box):
    def __init__(self):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8
        )
        self.set_name("notification-stack")
        self.notifications = {}

    def add_notification(self, notification: Notification, notification_center):
        view = NotificationView(notification_center)
        view.update_notification(notification)
        self.notifications[notification.id] = view
        self.prepend(view)
        view.show()

    def remove_notification(self, notification_id: int):
        if notification_id in self.notifications:
            view = self.notifications.pop(notification_id)
            self.remove(view)

    def clear(self):
        for view in self.notifications.values():
            self.remove(view)
        self.notifications.clear()

class NotificationView(Gtk.Box):
    def __init__(self, notification_center):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-box"
        )
        self.notification_center = notification_center
        
        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=200,
            name="notification-stack"
        )
        self.stack.set_hexpand(True)
        
        self.notification_pages = {}
        
        self.nav_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            halign=Gtk.Align.CENTER
        )
        self.prev_button = Gtk.Button(label="◀", name="prev-button")
        self.prev_button.get_style_context().add_class("flat")
        self.prev_button.get_style_context().add_class("white")
        self.prev_button.connect("clicked", self.on_prev_clicked)
        
        self.next_button = Gtk.Button(label="▶", name="next-button")
        self.next_button.get_style_context().add_class("flat")
        self.next_button.get_style_context().add_class("white")
        self.next_button.connect("clicked", self.on_next_clicked)
        
        self.nav_box.append(self.prev_button)
        self.nav_box.append(self.next_button)
        
        self.append(self.stack)
        self.append(self.nav_box)
        
        self.motion_controller = Gtk.EventControllerMotion()
        self.motion_controller.connect("enter", self.on_hover_enter)
        self.motion_controller.connect("leave", self.on_hover_leave)
        self.add_controller(self.motion_controller)
        
        self.is_hovered = False
    
    def create_notification_page(self, notification):
        page = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="notification-container",
            spacing=8
        )
        
        image = Gtk.Picture(name="notification-image")
        image.set_size_request(64, 64)
        image.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
        image.set_can_shrink(True)
        
        text_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-text"
        )
        text_box.set_valign(Gtk.Align.CENTER)
        
        summary_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="notification-summary-box"
        )
        summary_label = Gtk.Label(
            label=f"{notification.summary} | {notification.app_name}",
            name="notification-summary"
        )
        summary_label.set_halign(Gtk.Align.START)
        summary_label.set_ellipsize(Pango.EllipsizeMode.END)
        summary_label.set_max_width_chars(36)
        summary_box.append(summary_label)
        
        body_label = Gtk.Label(label=notification.body)
        body_label.set_halign(Gtk.Align.START)
        body_label.set_ellipsize(Pango.EllipsizeMode.END)
        body_label.set_max_width_chars(36)
        
        text_box.append(summary_box)
        text_box.append(body_label)
        
        close_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name="notification-close-box"
        )
        close_box.set_valign(Gtk.Align.CENTER)
        close_box.set_halign(Gtk.Align.END)
        
        close_button = Gtk.Button(label="×", name="notification-close-button")
        close_button.set_halign(Gtk.Align.CENTER)
        close_button.connect("clicked", self.on_close_clicked)
        close_button.get_style_context().add_class("circular")
        
        #close_box.append(close_button)
        
        page.append(image)
        page.append(text_box)
        text_box.set_hexpand(True)
        page.append(close_box)
        
        if notification.image_pixbuf:
            try:
                scaled_pixbuf = notification.image_pixbuf.scale_simple(64, 64, GdkPixbuf.InterpType.BILINEAR)
                texture = Gdk.Texture.new_for_pixbuf(scaled_pixbuf)
                image.set_paintable(texture)
                image.set_visible(True)
            except Exception as e:
                print(f"Error scaling image_pixbuf: {e}")
                image.set_visible(False)
        elif notification.app_icon and notification.app_icon.strip():
            if os.path.isfile(notification.app_icon):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        notification.app_icon, 64, 64, True)
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    image.set_paintable(texture)
                    image.set_visible(True)
                except Exception as e:
                    print(f"Error loading icon: {e}")
                    self._try_load_icon_name(image, notification.app_icon)
            else:
                self._try_load_icon_name(image, notification.app_icon)
        else:
            image.set_visible(False)
        
        return page
    
    def update_notification(self, notification):
        if notification.id not in self.notification_pages:
            page = self.create_notification_page(notification)
            self.notification_pages[notification.id] = page
            self.stack.add_named(page, str(notification.id))
        
        self.stack.set_visible_child_name(str(notification.id))
        self.notification = notification
    
    def _try_load_icon_name(self, image_widget, icon_name):
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        try:
            pixbuf = icon_theme.load_icon(icon_name, 64, 0)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image_widget.set_paintable(texture)
            image_widget.set_visible(True)
        except Exception as e:
            print(f"Error loading icon {icon_name}: {e}")
            try:
                pixbuf = icon_theme.load_icon("dialog-error", 64, 0)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                image_widget.set_paintable(texture)
                image_widget.set_visible(True)
            except:
                image_widget.set_visible(False)

    def on_close_clicked(self, button):
        self.notification_center.hide_notification()
        return True

    def on_prev_clicked(self, button):
        if hasattr(self.notification_center, "navigate_previous"):
            self.notification_center.navigate_previous()
            
    def on_next_clicked(self, button):
        if hasattr(self.notification_center, "navigate_next"):
            self.notification_center.navigate_next()
    
    def on_hover_enter(self, controller, x, y):
        self.is_hovered = True
        self.notification_center.on_notification_hover()
        
    def on_hover_leave(self, controller):
        self.is_hovered = False
        self.notification_center.on_notification_unhover()

class NotificationCenter:
    def __init__(self, notch):
        self.notch = notch
        self.history = []
        self.current_index = -1
        self.current_notification = None
        self.notification_queue = []
        self.is_showing = False
        self.notification_view = NotificationView(self)
        self.notifications = Notifications()
        
        self.notifications.connect('notification-added', self.on_notification_added)
        self.notifications.connect('notification-removed', self.on_notification_removed)
        self.notifications.connect('notification-closed', self.on_notification_closed)
        
        self.hide_timeout_id = None

    
    def display_notification(self, notification):
        """Display a notification and set a 5-second timeout"""
        self.current_notification = notification
        self.prepare_notification(notification)
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
        self.hide_timeout_id = GLib.timeout_add(5000, self.hide_notification)
        #GLib.timeout_add_seconds(1, self.notch.print_box_size)

    def on_notification_added(self, _, notification_id):
        notification = self.notifications.get_notification_from_id(notification_id)
        if notification:
            self.history.append(notification)
            self.current_index = len(self.history) - 1
            
            if self.is_showing:
                self.display_notification(notification)
                self.update_nav_buttons()
            else:
                self.notification_queue.append(notification)
                self.show_next_notification()
    
    def on_notification_removed(self, _, notification_id):
        self.history = [n for n in self.history if n.id != notification_id]
        if self.current_index >= len(self.history):
            self.current_index = len(self.history) - 1
        
        # Remove the notification page from the stack
        if notification_id in self.notification_view.notification_pages:
            page = self.notification_view.notification_pages.pop(notification_id)
            self.notification_view.stack.remove(page)
        
        if self.is_showing:
            if self.current_index >= 0 and self.history:
                self.display_notification(self.history[self.current_index])
            else:
                self.hide_notification()
        
        self.notification_queue = [n for n in self.notification_queue if n.id != notification_id]
        
        # Update navigation buttons
        self.update_nav_buttons()
    
    def on_notification_closed(self, _, notification_id, reason):
        if self.current_notification and self.current_notification.id == notification_id:
            self.hide_notification()
    
    def navigate_previous(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.display_notification(self.history[self.current_index])
            self.update_nav_buttons()
    
    def navigate_next(self):
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            self.display_notification(self.history[self.current_index])
            self.update_nav_buttons()
            
    def update_nav_buttons(self):
        self.notification_view.prev_button.set_sensitive(self.current_index > 0)
        self.notification_view.next_button.set_sensitive(self.current_index < len(self.history) - 1)
    
    def prepare_notification(self, notification):
        self.notification_view.update_notification(notification)
    
    def show_next_notification(self):
        if not self.notification_queue:
            return
        notification = self.notification_queue.pop(0)
        self.is_showing = True
        self.display_notification(notification)
        self.update_nav_buttons()
        self.notch.open_notch('notification')
    
    def hide_notification(self):
        if self.is_showing:
            if self.notch and self.notch.stack and self.notch.stack.get_visible_child_name() == "notification":

                self.notch.collapse_notch()
                self.is_showing = False
            
            if self.hide_timeout_id:
                GLib.source_remove(self.hide_timeout_id)
                self.hide_timeout_id = None
                
            if self.notification_queue:
                GLib.timeout_add(500, self.show_next_notification)
                
        return False
    
    def on_notification_hover(self):
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
            self.hide_timeout_id = None
    
    def on_notification_unhover(self):
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
        self.hide_timeout_id = GLib.timeout_add(5000, self.hide_notification)