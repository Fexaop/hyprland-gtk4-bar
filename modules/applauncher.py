import gi
from typing import Optional
import html

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gtk, Gio, GdkPixbuf, Gdk, Pango
from loguru import logger
from service.desktopapp import DesktopService, DesktopApp

class ApplicationRow(Gtk.ListBoxRow):
    """Custom row widget for displaying application info"""
    
    def __init__(self, app: DesktopApp):
        super().__init__()
        self.app = app
        self.set_activatable(True)
        self.set_selectable(True)
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        self.icon_image = Gtk.Image()
        self.icon_image.set_pixel_size(48)
        self.load_icon()
        
        label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label_box.set_hexpand(True)
        label_box.set_halign(Gtk.Align.START)
        label_box.set_valign(Gtk.Align.CENTER)
        
        name_label = Gtk.Label()
        app_name = app.name or "Unknown Application"
        name_label.set_text(app_name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_wrap(False)
        name_label.set_max_width_chars(40)
        escaped_name = html.escape(app_name)
        name_label.set_markup(f"<b>{escaped_name}</b>")
        
        desc_label = None
        if app.description and app.description.strip():
            desc_label = Gtk.Label()
            desc_label.set_text(app.description)
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_ellipsize(Pango.EllipsizeMode.END)
            desc_label.set_wrap(False)
            desc_label.set_max_width_chars(50)
            escaped_desc = html.escape(app.description)
            desc_label.set_markup(f"<small><span foreground='--foreground'>{escaped_desc}</span></small>")
        elif app.generic_name and app.generic_name.strip() and app.generic_name != app.name:
            desc_label = Gtk.Label()
            desc_label.set_text(app.generic_name)
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_ellipsize(Pango.EllipsizeMode.END)
            desc_label.set_wrap(False)
            desc_label.set_max_width_chars(50)
            escaped_generic = html.escape(app.generic_name)
            desc_label.set_markup(f"<small><span foreground='--foreground'>{escaped_generic}</span></small>")
        
        label_box.append(name_label)
        if desc_label:
            label_box.append(desc_label)
        
        box.append(self.icon_image)
        box.append(label_box)
        
        self.set_child(box)
    
    def load_icon(self):
        """Load and set the application icon using system icon theme"""
        try:
            display = Gdk.Display.get_default()
            if display:
                icon_theme = Gtk.IconTheme.get_for_display(display)
            else:
                icon_theme = Gtk.IconTheme.new()
            
            icon_name = None
            if self.app.icon:
                if hasattr(self.app.icon, 'get_names'):
                    names = self.app.icon.get_names()
                    if names and len(names) > 0:
                        icon_name = names[0]
                elif hasattr(self.app.icon, 'to_string'):
                    icon_name = self.app.icon.to_string()
            
            if not icon_name and self.app.icon_name:
                icon_name = self.app.icon_name
            
            if icon_name:
                if '/' in icon_name:
                    icon_name = icon_name.split('/')[-1]
                if '.' in icon_name and icon_name.endswith(('.png', '.svg', '.xpm', '.ico')):
                    icon_name = icon_name.rsplit('.', 1)[0]
                
                if icon_theme.has_icon(icon_name):
                    icon_paintable = icon_theme.lookup_icon(
                        icon_name,
                        None,
                        48,
                        1,
                        Gtk.TextDirection.NONE,
                        Gtk.IconLookupFlags.FORCE_REGULAR
                    )
                    if icon_paintable:
                        self.icon_image.set_from_paintable(icon_paintable)
                        return
                
                self.icon_image.set_from_icon_name(icon_name)
                return
            
            fallback_icons = [
                "application-x-executable",
                "application-default-icon",
                "application-x-desktop",
                "exec",
                "system-run",
                "preferences-desktop-applications"
            ]
            
            for fallback in fallback_icons:
                if icon_theme.has_icon(fallback):
                    self.icon_image.set_from_icon_name(fallback)
                    return
            
            self.icon_image.set_from_icon_name("application-x-executable")
            
        except Exception as e:
            logger.warning(f"Failed to load icon for {self.app.name}: {e}")
            self.icon_image.set_from_icon_name("application-x-executable")

class ApplicationLauncherBox(Gtk.Box):
    """A box containing an application launcher with search and list of apps"""
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.desktop_service = DesktopService()
        self.set_name("applauncher")
        toolbar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toolbar_box.set_margin_top(6)
        toolbar_box.set_margin_bottom(6)
        toolbar_box.set_margin_start(12)
        toolbar_box.set_margin_end(12)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search applications...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self.on_search_changed)
        
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_search_key_pressed)
        self.search_entry.add_controller(key_controller)
        
        toolbar_box.append(self.search_entry)
        
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.set_vexpand(True)
        
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect("row-activated", self.on_row_activated)
        
        self.list_box.set_margin_start(6)
        self.list_box.set_margin_end(6)
        self.list_box.set_margin_top(6)
        self.list_box.set_margin_bottom(6)
        
        self.scrolled_window.set_child(self.list_box)
        
        self.append(toolbar_box)
        self.append(self.scrolled_window)
        
        self.load_applications()
    
    def load_applications(self):
        """Load all desktop applications into the list"""
        try:
            child = self.list_box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.list_box.remove(child)
                child = next_child
            
            apps = self.desktop_service.get_applications(include_hidden=False)
            apps.sort(key=lambda app: (app.name or "").lower())
            
            for app in apps:
                if app.name:
                    row = ApplicationRow(app)
                    self.list_box.append(row)
            
            logger.info(f"Loaded {len(apps)} applications")
            
        except Exception as e:
            logger.error(f"Failed to load applications: {e}")
            error_label = Gtk.Label()
            error_label.set_text(f"Error loading applications: {e}")
            error_label.set_margin_top(24)
            error_label.set_margin_bottom(24)
            self.list_box.append(error_label)
    
    def on_search_changed(self, search_entry: Gtk.SearchEntry):
        """Handle search text changes"""
        search_text = search_entry.get_text().strip()
        
        child = self.list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.list_box.remove(child)
            child = next_child
        
        if not search_text:
            self.load_applications()
            return
        
        try:
            filtered_apps = self.desktop_service.search_applications(search_text, include_hidden=False)
            filtered_apps.sort(key=lambda app: (app.name or "").lower())
            
            for app in filtered_apps:
                if app.name:
                    row = ApplicationRow(app)
                    self.list_box.append(row)
            
            if not filtered_apps:
                no_results_label = Gtk.Label()
                no_results_label.set_text("No applications found")
                no_results_label.set_margin_top(24)
                no_results_label.set_margin_bottom(24)
                self.list_box.append(no_results_label)
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
    
    def on_search_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses in the search entry for navigation"""
        if keyval == Gdk.KEY_Down:
            selected_row = self.list_box.get_selected_row()
            if selected_row:
                next_row = selected_row.get_next_sibling()
                if next_row:
                    self.list_box.select_row(next_row)
            else:
                first_row = self.list_box.get_first_child()
                if first_row:
                    self.list_box.select_row(first_row)
            return True
        elif keyval == Gdk.KEY_Up:
            selected_row = self.list_box.get_selected_row()
            if selected_row:
                prev_row = selected_row.get_prev_sibling()
                if prev_row:
                    self.list_box.select_row(prev_row)
            return True
        elif keyval == Gdk.KEY_Return:
            selected_row = self.list_box.get_selected_row()
            if selected_row:
                self.list_box.emit("row-activated", selected_row)
            return True
        return False
    
    def on_row_activated(self, list_box: Gtk.ListBox, row: ApplicationRow):
        """Handle application launch when row is clicked"""
        try:
            logger.info(f"Launching application: {row.app.name}")
            success = row.app.launch()
            if success:
                logger.info(f"Successfully launched {row.app.name}")
            else:
                logger.error(f"Failed to launch {row.app.name}")
                self.show_error_dialog(f"Failed to launch {row.app.name}")
                
        except Exception as e:
            logger.error(f"Error launching {row.app.name}: {e}")
            self.show_error_dialog(f"Error launching {row.app.name}: {e}")
    
    def show_error_dialog(self, message: str):
        """Show an error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Launch Error"
        )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()