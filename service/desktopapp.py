import gi
import shlex
from dataclasses import dataclass
from typing import Callable, Any
from loguru import logger

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gtk, Gio, GdkPixbuf, GLib


@dataclass(init=False)
class DesktopApp:
    """Desktop application wrapper for GTK4"""
    name: str
    generic_name: str | None
    display_name: str | None
    description: str | None
    window_class: str | None
    executable: str | None
    command_line: str | None
    icon: (
        Gio.Icon
        | Gio.ThemedIcon
        | Gio.FileIcon
        | Gio.LoadableIcon
        | Gio.EmblemedIcon
        | None
    )
    icon_name: str | None
    hidden: bool

    def __init__(
        self, app: Gio.DesktopAppInfo, icon_theme: Gtk.IconTheme | None = None
    ):
        self._app: Gio.DesktopAppInfo = app
        self._icon_theme = icon_theme or Gtk.IconTheme.get_for_display(
            display=Gtk.Widget.get_default_direction() and 
            Gtk.Widget.get_default_direction().get_display() or 
            Gio.Application.get_default().get_dbus_connection().get_peer_credentials().get_unix_user()
        ) if hasattr(Gtk, 'Widget') else Gtk.IconTheme.new()
        self._pixbuf: GdkPixbuf.Pixbuf | None = None
        self.name = app.get_name()
        self.generic_name = app.get_generic_name()
        self.display_name = app.get_display_name()
        self.description = app.get_description()
        self.window_class = app.get_startup_wm_class()
        self.executable = app.get_executable()
        self.command_line = app.get_commandline()
        self.icon = app.get_icon()
        self.icon_name = self.icon.to_string() if self.icon is not None else None
        self.hidden = app.get_is_hidden()

    def launch(self):
        """Launch the desktop application"""
        return self._app.launch()

    def get_icon_texture(
        self,
        size: int = 48,
        default_icon: str | None = "image-missing",
        flags: Gtk.IconLookupFlags = Gtk.IconLookupFlags.FORCE_REGULAR,
    ) -> Gtk.IconPaintable | None:
        """
        Get an icon texture from the icon (GTK4 uses IconPaintable instead of Pixbuf)

        :param size: the size of the icon, defaults to 48
        :type size: int, optional
        :param default_icon: the name of the default icon, defaults to "image-missing"
        :type default_icon: str | None, optional
        :param flags: the Gtk.IconLookupFlags to use when fetching the icon
        :type flags: Gtk.IconLookupFlags, optional
        :return: the icon paintable
        :rtype: Gtk.IconPaintable | None
        """
        try:
            if not self.icon_name:
                raise ValueError("No icon name available")
            
            return self._icon_theme.lookup_icon(
                self.icon_name,
                None,  # fallbacks
                size,
                1,     # scale
                Gtk.TextDirection.NONE,
                flags,
            )
        except Exception as e:
            logger.warning(f"Failed to load icon {self.icon_name}: {e}")
            if default_icon:
                try:
                    return self._icon_theme.lookup_icon(
                        default_icon,
                        None,
                        size,
                        1,
                        Gtk.TextDirection.NONE,
                        flags,
                    )
                except Exception:
                    pass
            return None

    def get_icon_pixbuf(
        self,
        size: int = 48,
        default_icon: str | None = "image-missing",
        flags: Gtk.IconLookupFlags = Gtk.IconLookupFlags.FORCE_REGULAR,
    ) -> GdkPixbuf.Pixbuf | None:
        """
        Get a pixbuf from the icon (compatibility method)

        :param size: the size of the icon, defaults to 48
        :type size: int, optional
        :param default_icon: the name of the default icon, defaults to "image-missing"
        :type default_icon: str | None, optional
        :param flags: the Gtk.IconLookupFlags to use when fetching the icon
        :type flags: Gtk.IconLookupFlags, optional
        :return: the pixbuf
        :rtype: GdkPixbuf.Pixbuf | None
        """
        if self._pixbuf:
            return self._pixbuf
        
        try:
            icon_paintable = self.get_icon_texture(size, default_icon, flags)
            if icon_paintable:
                # Convert IconPaintable to Pixbuf if needed
                # This is a simplified conversion - in real GTK4 apps you'd work with paintables directly
                self._pixbuf = icon_paintable.get_file().load(size, size, None)[0] if hasattr(icon_paintable, 'get_file') else None
        except Exception as e:
            logger.warning(f"Failed to convert icon to pixbuf: {e}")
            
        return self._pixbuf


def get_desktop_applications(include_hidden: bool = False) -> list[DesktopApp]:
    """
    Get a list of all desktop applications
    This might be useful for writing application launchers

    :param include_hidden: whether to include applications unintended to be visible to normal users, defaults to False
    :type include_hidden: bool, optional
    :return: a list of all desktop applications
    :rtype: list[DesktopApp]
    """
    try:
        icon_theme = Gtk.IconTheme.new()
        # In GTK4, we need to set the theme manually if needed
        # icon_theme.set_theme_name("Adwaita")  # or detect system theme
    except Exception:
        icon_theme = None
        logger.warning("Failed to create icon theme, icons may not work properly")
    
    return [
        DesktopApp(app, icon_theme)
        for app in Gio.DesktopAppInfo.get_all()
        if include_hidden or app.should_show()
    ]


def exec_shell_command_async(
    cmd: str | list[str],
    callback: Callable[[str], Any] | None = None,
) -> tuple[Gio.Subprocess | None, Gio.DataInputStream | None]:
    """
    Execute a shell command and returns the output asynchronously

    :param cmd: the shell command to execute
    :type cmd: str | list[str]
    :param callback: a function to retrieve the result or None to ignore the result
    :type callback: Callable[[str], Any] | None, optional
    :return: a Gio.Subprocess object and a Gio.DataInputStream object for stdout
    :rtype: tuple[Gio.Subprocess | None, Gio.DataInputStream | None]
    """
    try:
        process = Gio.Subprocess.new(
            shlex.split(cmd) if isinstance(cmd, str) else cmd,
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE,
        )

        if not process:
            logger.error(f"Failed to create subprocess for command: {cmd}")
            return None, None

        stdout_pipe = process.get_stdout_pipe()
        if not stdout_pipe:
            logger.error("Failed to get stdout pipe from subprocess")
            return process, None

        stdout = Gio.DataInputStream(
            base_stream=stdout_pipe,
            close_base_stream=True,
        )

        def reader_loop(stdout: Gio.DataInputStream):
            def read_line(stream: Gio.DataInputStream, result: Gio.AsyncResult):
                try:
                    output, length = stream.read_line_finish_utf8(result)
                    if output is not None and isinstance(output, str):
                        if callback:
                            callback(output)
                        reader_loop(stream)
                    # If output is None, the stream has ended
                except Exception as e:
                    logger.error(f"Error reading from subprocess: {e}")

            stdout.read_line_async(GLib.PRIORITY_DEFAULT, None, read_line)

        reader_loop(stdout)
        return process, stdout

    except Exception as e:
        logger.error(f"Error executing command '{cmd}': {e}")
        return None, None


def idle_add(func: Callable, *args, pin: bool = False) -> int:
    """
    Add a function to be invoked in a lazy manner in the main thread, useful for multi-threaded code

    :param func: the function to be queued
    :type func: Callable
    :param args: arguments will be passed to the given function
    :param pin: whether the function should be invoked as long as its return value is True
    :type pin: bool, optional
    :return: the source ID that can be used to remove the idle handler
    :rtype: int
    """
    if pin:
        return GLib.idle_add(func, *args)

    def idle_executor(*largs):
        try:
            func(*largs)
        except Exception as e:
            logger.error(f"Error in idle function: {e}")
        return False  # Don't repeat

    return GLib.idle_add(idle_executor, *args)


def remove_handler(handler_id: int) -> bool:
    """
    Remove a GLib source handler

    :param handler_id: the handler ID returned by idle_add or other GLib functions
    :type handler_id: int
    :return: True if the source was found and removed
    :rtype: bool
    """
    return GLib.source_remove(handler_id)


class DesktopService:
    """
    A service class that provides desktop application management functionality
    """
    
    def __init__(self):
        self._applications: list[DesktopApp] | None = None
        self._icon_theme: Gtk.IconTheme | None = None
        self._handlers: list[int] = []
    
    def get_applications(self, include_hidden: bool = False, refresh: bool = False) -> list[DesktopApp]:
        """
        Get desktop applications with caching
        
        :param include_hidden: include hidden applications
        :type include_hidden: bool
        :param refresh: force refresh of the applications list
        :type refresh: bool
        :return: list of desktop applications
        :rtype: list[DesktopApp]
        """
        if self._applications is None or refresh:
            self._applications = get_desktop_applications(include_hidden)
        return self._applications
    
    def search_applications(self, query: str, include_hidden: bool = False) -> list[DesktopApp]:
        """
        Search applications by name, description, or executable
        
        :param query: search query
        :type query: str
        :param include_hidden: include hidden applications
        :type include_hidden: bool
        :return: filtered list of applications
        :rtype: list[DesktopApp]
        """
        applications = self.get_applications(include_hidden)
        query_lower = query.lower()
        
        return [
            app for app in applications
            if (app.name and query_lower in app.name.lower()) or
               (app.description and query_lower in app.description.lower()) or
               (app.executable and query_lower in app.executable.lower()) or
               (app.generic_name and query_lower in app.generic_name.lower())
        ]
    
    def execute_command_async(
        self, 
        command: str | list[str], 
        on_output: Callable[[str], Any] | None = None
    ) -> tuple[Gio.Subprocess | None, Gio.DataInputStream | None]:
        """
        Execute a command asynchronously
        
        :param command: command to execute
        :type command: str | list[str]
        :param on_output: callback for output lines
        :type on_output: Callable[[str], Any] | None
        :return: subprocess and data stream
        :rtype: tuple[Gio.Subprocess | None, Gio.DataInputStream | None]
        """
        return exec_shell_command_async(command, on_output)
    
    def schedule_idle(self, func: Callable, *args, pin: bool = False) -> int:
        """
        Schedule a function to run in the main thread
        
        :param func: function to schedule
        :type func: Callable
        :param args: function arguments
        :param pin: whether to repeat while function returns True
        :type pin: bool
        :return: handler ID
        :rtype: int
        """
        handler_id = idle_add(func, *args, pin=pin)
        self._handlers.append(handler_id)
        return handler_id
    
    def remove_handler(self, handler_id: int) -> bool:
        """
        Remove a scheduled handler
        
        :param handler_id: handler ID to remove
        :type handler_id: int
        :return: True if removed successfully
        :rtype: bool
        """
        if handler_id in self._handlers:
            self._handlers.remove(handler_id)
        return remove_handler(handler_id)
    
    def cleanup(self):
        """Clean up all scheduled handlers"""
        for handler_id in self._handlers:
            remove_handler(handler_id)
        self._handlers.clear()


# Example usage
if __name__ == "__main__":
    # Initialize GTK
    Gtk.init()
    
    # Create service
    service = DesktopService()
    
    # Get all applications
    apps = service.get_applications()
    print(f"Found {len(apps)} applications")
    
    # Search for applications
    firefox_apps = service.search_applications("firefox")
    print(f"Found {len(firefox_apps)} Firefox-related apps")
    
    # Execute a command
    def on_output(line: str):
        print(f"Command output: {line.strip()}")
    
    proc, stream = service.execute_command_async("echo 'Hello GTK4!'", on_output)
    
    # Schedule an idle function
    def idle_task():
        print("Idle task executed")
        return False  # Don't repeat
    
    handler_id = service.schedule_idle(idle_task)
    
    # Clean up
    service.cleanup()