import gi
from typing import Optional
import html
import os
import time

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gtk, Gio, GdkPixbuf, Gdk, Pango, GObject
from loguru import logger
from service.desktopapp import DesktopService, DesktopApp

class AppModel(GObject.Object):
    """Model object for holding application data"""
    
    def __init__(self, app: DesktopApp):
        super().__init__()
        self.app = app
        self.last_used = self.get_last_used_time()
    
    def get_last_used_time(self) -> float:
        """Get the last used time for the application"""
        try:
            # Try to get from .desktop file's access time or a usage tracking file
            desktop_file = getattr(self.app, 'desktop_file', None)
            if desktop_file and os.path.exists(desktop_file):
                return os.path.getmtime(desktop_file)
            
            # Fallback: check if there's a usage tracking directory
            usage_dir = os.path.expanduser("~/.local/share/recently-used-apps")
            if os.path.exists(usage_dir):
                app_id = self.app.app_id or self.app.name
                if app_id:
                    usage_file = os.path.join(usage_dir, f"{app_id}.timestamp")
                    if os.path.exists(usage_file):
                        return os.path.getmtime(usage_file)
        except Exception as e:
            logger.debug(f"Could not get last used time for {self.app.name}: {e}")
        
        # Default to 0 if we can't determine usage
        return 0.0
    
    def update_last_used(self):
        """Update the last used timestamp"""
        self.last_used = time.time()
        
        # Create usage tracking directory if it doesn't exist
        usage_dir = os.path.expanduser("~/.local/share/recently-used-apps")
        os.makedirs(usage_dir, exist_ok=True)
        
        # Write timestamp file
        app_id = self.app.app_id or self.app.name
        if app_id:
            usage_file = os.path.join(usage_dir, f"{app_id}.timestamp")
            try:
                with open(usage_file, 'w') as f:
                    f.write(str(self.last_used))
            except Exception as e:
                logger.debug(f"Could not write usage timestamp for {app_id}: {e}")

class ApplicationRowWidget(Gtk.Box):
    """Widget for displaying application info in ListView"""
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(12)
        self.set_margin_end(12)
        
        self.icon_image = Gtk.Image()
        self.icon_image.set_pixel_size(48)
        
        label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label_box.set_hexpand(True)
        label_box.set_halign(Gtk.Align.START)
        label_box.set_valign(Gtk.Align.CENTER)
        
        self.name_label = Gtk.Label()
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.set_wrap(False)
        self.name_label.set_max_width_chars(40)
        
        self.desc_label = Gtk.Label()
        self.desc_label.set_halign(Gtk.Align.START)
        self.desc_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.desc_label.set_wrap(False)
        self.desc_label.set_max_width_chars(50)
        
        label_box.append(self.name_label)
        label_box.append(self.desc_label)
        
        self.append(self.icon_image)
        self.append(label_box)
        
        self.app_model = None
    
    def bind(self, app_model: AppModel):
        """Bind the widget to an app model"""
        self.app_model = app_model
        app = app_model.app
        
        # Set name
        app_name = app.name or "Unknown Application"
        escaped_name = html.escape(app_name)
        self.name_label.set_markup(f"<b>{escaped_name}</b>")
        
        # Set description - Fixed color specification
        if app.description and app.description.strip():
            escaped_desc = html.escape(app.description)
            # Option 1: Use a dimmed/secondary text color
            self.desc_label.set_markup(f"<small><span foreground='#888888'>{escaped_desc}</span></small>")
            self.desc_label.set_visible(True)
        elif app.generic_name and app.generic_name.strip() and app.generic_name != app.name:
            escaped_generic = html.escape(app.generic_name)
            # Option 1: Use a dimmed/secondary text color
            self.desc_label.set_markup(f"<small><span foreground='#888888'>{escaped_generic}</span></small>")
            self.desc_label.set_visible(True)
        else:
            self.desc_label.set_visible(False)
        
        # Load icon
        self.load_icon(app)
    
    def load_icon(self, app: DesktopApp):
        """Load and set the application icon"""
        try:
            display = Gdk.Display.get_default()
            if display:
                icon_theme = Gtk.IconTheme.get_for_display(display)
            else:
                icon_theme = Gtk.IconTheme.new()
            
            icon_name = None
            if app.icon:
                if hasattr(app.icon, 'get_names'):
                    names = app.icon.get_names()
                    if names and len(names) > 0:
                        icon_name = names[0]
                elif hasattr(app.icon, 'to_string'):
                    icon_name = app.icon.to_string()
            
            if not icon_name and app.icon_name:
                icon_name = app.icon_name
            
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
            logger.warning(f"Failed to load icon for {app.name}: {e}")
            self.icon_image.set_from_icon_name("application-x-executable")

class ApplicationLauncherBox(Gtk.Box):
    """A box containing an application launcher with search and list of apps"""
    
    def __init__(self, notch):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.desktop_service = DesktopService()
        self.set_name("applauncher")
        
        # Create toolbar
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
        
        # Create list model
        self.list_store = Gio.ListStore.new(AppModel)
        self.filter_model = Gtk.FilterListModel.new(self.list_store, None)
        self.sort_model = Gtk.SortListModel.new(self.filter_model, None)
        
        # Create sorter for most recent usage
        self.sorter = Gtk.CustomSorter.new(self.compare_apps, None)
        self.sort_model.set_sorter(self.sorter)
        
        # Create selection model
        self.selection_model = Gtk.SingleSelection.new(self.sort_model)
        
        # Create list view
        self.list_view = Gtk.ListView.new(self.selection_model, None)
        
        # Create factory for list items
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.on_factory_setup)
        factory.connect("bind", self.on_factory_bind)
        factory.connect("unbind", self.on_factory_unbind)
        self.list_view.set_factory(factory)
        
        # Set up activation
        self.list_view.connect("activate", self.on_item_activated)
        
        # Create scrolled window
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.set_child(self.list_view)
        
        # Add margins to the scrolled window
        self.scrolled_window.set_margin_start(6)
        self.scrolled_window.set_margin_end(6)
        self.scrolled_window.set_margin_top(6)
        self.scrolled_window.set_margin_bottom(6)
        
        self.append(toolbar_box)
        self.append(self.scrolled_window)
        
        self.load_applications()
    
    def compare_apps(self, app1: AppModel, app2: AppModel, user_data) -> int:
        """Compare function for sorting apps by most recent usage"""
        # Sort by last used time (descending - most recent first)
        if app1.last_used > app2.last_used:
            return -1
        elif app1.last_used < app2.last_used:
            return 1
        else:
            # If same usage time, sort alphabetically by name
            name1 = (app1.app.name or "").lower()
            name2 = (app2.app.name or "").lower()
            if name1 < name2:
                return -1
            elif name1 > name2:
                return 1
            else:
                return 0
    
    def on_factory_setup(self, factory, list_item):
        """Set up the list item widget"""
        widget = ApplicationRowWidget()
        list_item.set_child(widget)
    
    def on_factory_bind(self, factory, list_item):
        """Bind data to the list item widget"""
        app_model = list_item.get_item()
        widget = list_item.get_child()
        widget.bind(app_model)
    
    def on_factory_unbind(self, factory, list_item):
        """Unbind data from the list item widget"""
        widget = list_item.get_child()
        widget.app_model = None
    
    def load_applications(self):
        """Load all desktop applications into the list"""
        try:
            # Clear existing items
            self.list_store.remove_all()
            
            apps = self.desktop_service.get_applications(include_hidden=False)
            
            # Create AppModel objects and add to store
            for app in apps:
                if app.name:
                    app_model = AppModel(app)
                    self.list_store.append(app_model)
            
            logger.info(f"Loaded {len(apps)} applications")
            
        except Exception as e:
            logger.error(f"Failed to load applications: {e}")
    
    def on_search_changed(self, search_entry: Gtk.SearchEntry):
        """Handle search text changes"""
        search_text = search_entry.get_text().strip().lower()
        
        if not search_text:
            # Remove filter to show all apps
            self.filter_model.set_filter(None)
        else:
            # Create filter for search text
            filter_func = Gtk.CustomFilter.new(self.filter_apps, search_text)
            self.filter_model.set_filter(filter_func)
    
    def filter_apps(self, app_model: AppModel, search_text: str) -> bool:
        """Filter function for search"""
        app = app_model.app
        search_text = search_text.lower()
        
        # Check name
        if app.name and search_text in app.name.lower():
            return True
        
        # Check description
        if app.description and search_text in app.description.lower():
            return True
        
        # Check generic name
        if app.generic_name and search_text in app.generic_name.lower():
            return True
        
        # Check keywords
        if hasattr(app, 'keywords') and app.keywords:
            for keyword in app.keywords:
                if search_text in keyword.lower():
                    return True
        
        return False
    
    def on_search_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses in the search entry for navigation"""
        if keyval == Gdk.KEY_Down:
            current_pos = self.selection_model.get_selected()
            n_items = self.selection_model.get_n_items()
            if current_pos < n_items - 1:
                self.selection_model.set_selected(current_pos + 1)
            elif n_items > 0:
                self.selection_model.set_selected(0)
            return True
        elif keyval == Gdk.KEY_Up:
            current_pos = self.selection_model.get_selected()
            if current_pos > 0:
                self.selection_model.set_selected(current_pos - 1)
            else:
                n_items = self.selection_model.get_n_items()
                if n_items > 0:
                    self.selection_model.set_selected(n_items - 1)
            return True
        elif keyval == Gdk.KEY_Return:
            selected_pos = self.selection_model.get_selected()
            if selected_pos != Gtk.INVALID_LIST_POSITION:
                self.list_view.emit("activate", selected_pos)
            return True
        return False
    
    def on_item_activated(self, list_view, position):
        """Handle application launch when item is activated"""
        try:
            app_model = self.selection_model.get_item(position)
            if not app_model:
                return
            
            app = app_model.app
            logger.info(f"Launching application: {app.name}")
            
            success = app.launch()
            if success:
                logger.info(f"Successfully launched {app.name}")
                # Update last used time
                app_model.update_last_used()
                # Re-sort the list to reflect new usage
                self.sorter.changed(Gtk.SorterChange.DIFFERENT)
            else:
                logger.error(f"Failed to launch {app.name}")
                self.show_error_dialog(f"Failed to launch {app.name}")
                
        except Exception as e:
            logger.error(f"Error launching application: {e}")
            self.show_error_dialog(f"Error launching application: {e}")
    
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