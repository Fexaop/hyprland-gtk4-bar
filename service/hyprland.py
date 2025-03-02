import json
import os
import socket
import threading
import time
from typing import Any, Optional, Callable

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GLib', '2.0')
from gi.repository import GObject, GLib, Gio

from .constants import HYPR_SOCKET_DIR


class HyprlandIPCNotFoundError(Exception):
    """Raised when Hyprland IPC socket is not found."""
    pass


class HyprlandService(GObject.Object):
    """
    Hyprland IPC client using native GTK4.
    
    Connects to Hyprland's socket to send commands and receive events.
    Provides properties that update when Hyprland state changes.
    
    Example usage:
    
    ```python
    from service.hyprland import HyprlandService
    
    hyprland = HyprlandService.get_default()
    
    print(hyprland.get_workspaces())
    print(hyprland.get_kb_layout())
    
    hyprland.connect("notify::kb-layout", lambda obj, pspec: print(obj.get_kb_layout()))
    ```
    """
    
    # Define properties
    __gsignals__ = {
        'workspaces-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'active-workspace-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'kb-layout-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'active-window-changed': (GObject.SignalFlags.RUN_FIRST, None, ())
    }
    
    # Define GObject properties
    workspaces = GObject.Property(type=object, default=None)
    active_workspace = GObject.Property(type=object, default=None)
    kb_layout = GObject.Property(type=str, default="")
    active_window = GObject.Property(type=object, default=None)
    
    # Singleton pattern
    _instance = None
    
    @classmethod
    def get_default(cls):
        """Get or create the singleton instance of HyprlandService."""
        if cls._instance is None:
            cls._instance = HyprlandService()
        return cls._instance
    
    def __init__(self):
        """Initialize the HyprlandService."""
        GObject.Object.__init__(self)
        
        # Initialize properties
        self._workspaces: list[dict[str, Any]] = []
        self._active_workspace: dict[str, Any] = {}
        self._kb_layout: str = ""
        self._active_window: dict[str, Any] = {}
        
        # For tracking window changes
        self._last_window_address = None
        self._auto_sync_enabled = True
        self._event_thread_running = False
        
        # Connect to Hyprland if available
        if self.is_available():
            # Initial sync
            self._sync_kb_layout()
            self._sync_workspaces()
            self._sync_active_window()
            
            # Start event listener
            self._listen_events()
    
    def is_available(self) -> bool:
        """Check if Hyprland IPC is available."""
        return os.path.exists(HYPR_SOCKET_DIR)
    
    def get_workspaces(self) -> list[dict[str, Any]]:
        """Get list of workspaces."""
        return self._workspaces
    
    def get_active_workspace(self) -> dict[str, Any]:
        """Get the currently active workspace."""
        return self._active_workspace
    
    def get_kb_layout(self) -> str:
        """Get the current keyboard layout."""
        return self._kb_layout
    
    def get_active_window(self) -> dict[str, Any]:
        """Get the currently focused window."""
        return self._active_window
    
    def _listen_events(self) -> None:
        """Start listening for events from Hyprland IPC in a separate thread."""
        if not self._event_thread_running:
            self._event_thread_running = True
            thread = threading.Thread(target=self._listen_events_thread, daemon=True)
            thread.start()
    
    def _listen_events_thread(self) -> None:
        """Thread function to listen for events from Hyprland."""
        while self._event_thread_running:
            try:
                # Connect to the event socket
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.connect(f"{HYPR_SOCKET_DIR}/.socket2.sock")
                    sock.setblocking(True)
                    
                    buffer = ""
                    while self._event_thread_running:
                        try:
                            data = sock.recv(4096).decode('utf-8')
                            if not data:
                                break
                            
                            # Append to buffer and process complete lines
                            buffer += data
                            lines = buffer.split('\n')
                            
                            # Process complete lines
                            for i in range(len(lines) - 1):
                                if lines[i]:
                                    # Schedule event processing on main thread
                                    GLib.idle_add(self._on_event_received, lines[i])
                            
                            # Keep partial line in buffer
                            buffer = lines[-1]
                            
                        except socket.error as e:
                            print(f"Socket error: {e}, will retry...")
                            break
                
                # Wait a bit before retrying
                time.sleep(1)
                
            except Exception as e:
                print(f"Error in Hyprland event listener: {e}")
                # Wait before retry
                time.sleep(1)
    
    def _on_event_received(self, event: str) -> None:
        """Handle received events from Hyprland."""
        event = event.strip()
        
        # Extract event type and data
        event_parts = event.split(">>")
        # Extract event type and data
        event_parts = event.split(">>")
        event_type = event_parts[0] if event_parts else ""
        event_data = event_parts[1] if len(event_parts) > 1 else ""
        
        # Handle workspace events
        if event_type in ["workspace", "createworkspace", "destroyworkspace", 
                          "renameworkspace", "moveworkspace", "focusedmon"]:
            self._sync_workspaces()
        
        # Handle keyboard layout events
        elif event_type == "activelayout":
            self._sync_kb_layout()
        
        # Handle window events
        elif event_type in ["activewindow", "windowtitle", "closewindow", 
                           "movewindow", "openwindow", "fullscreen", "windowfocus"]:
            # For window-related events, sync both window and workspaces
            # Windows events can affect workspace counts
            self._sync_active_window()
            self._sync_workspaces()
            
        # Handle special events for windows on specific workspaces
        elif event_type in ["windowclose", "windowopen"]:
            # These events directly inform us about window count changes
            self._sync_workspaces()
        
        return False  # Return False to remove from idle queue
    
    def _sync_workspaces(self) -> None:
        """Sync workspaces information from Hyprland."""
        if not self._auto_sync_enabled:
            return
            
        try:
            self._workspaces = sorted(
                json.loads(self.send_command("j/workspaces")), key=lambda x: x["id"]
            )
            self._active_workspace = json.loads(self.send_command("j/activeworkspace"))
            
            # Update GObject properties
            self.props.workspaces = self._workspaces
            self.props.active_workspace = self._active_workspace
            
            # Emit signals
            self.emit("workspaces-changed")
            self.emit("active-workspace-changed")
        except Exception as e:
            print(f"Error syncing workspaces: {e}")
    
    def _sync_kb_layout(self) -> None:
        """Sync keyboard layout information from Hyprland."""
        if not self._auto_sync_enabled:
            return
            
        try:
            for kb in json.loads(self.send_command("j/devices"))["keyboards"]:
                if kb["main"]:
                    self._kb_layout = kb["active_keymap"]
                    self.props.kb_layout = self._kb_layout
                    self.emit("kb-layout-changed")
                    break
        except Exception as e:
            print(f"Error syncing keyboard layout: {e}")
    
    def _sync_active_window(self) -> None:
        """Sync active window information from Hyprland."""
        if not self._auto_sync_enabled:
            return
            
        try:
            self._active_window = json.loads(self.send_command("j/activewindow"))
            self._last_window_address = self._active_window.get("address")
            self.props.active_window = self._active_window
            self.emit("active-window-changed")
        except Exception as e:
            print(f"Error syncing active window: {e}")
    
    def send_command(self, cmd: str) -> str:
        """
        Send a command to the Hyprland IPC.
        Supports the same commands as `hyprctl`.
        If you want to receive the response in JSON format, use this syntax: `j/COMMAND`.
        
        Args:
            cmd: The command to send.
            
        Returns:
            Response from Hyprland IPC.
            
        Raises:
            HyprlandIPCNotFoundError: If Hyprland IPC is not found.
        """
        if not self.is_available():
            raise HyprlandIPCNotFoundError()
        
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(f"{HYPR_SOCKET_DIR}/.socket.sock")
                sock.send(cmd.encode('utf-8'))
                
                response = b""
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    response += data
                
                return response.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Error sending command to Hyprland: {e}")
            return ""
    
    def switch_kb_layout(self) -> None:
        """Switch to the next keyboard layout."""
        try:
            for kb in json.loads(self.send_command("j/devices"))["keyboards"]:
                if kb["main"]:
                    self.send_command(f"dispatch switchxkblayout {kb['name']} next")
                    break
        except Exception as e:
            print(f"Error switching keyboard layout: {e}")
    
    def switch_to_workspace(self, workspace_id: int) -> None:
        """
        Switch to a workspace by its ID.
        
        Args:
            workspace_id: The ID of the workspace to switch to.
        """
        try:
            self.send_command(f"dispatch workspace {workspace_id}")
        except Exception as e:
            print(f"Error switching to workspace {workspace_id}: {e}")
    
    def enable_auto_sync(self, enabled: bool = True) -> None:
        """
        Enable or disable automatic syncing.
        
        When disabled, events will still be received but won't trigger updates.
        To manually update, use the sync methods directly.
        """
        self._auto_sync_enabled = enabled
    
    def cleanup(self) -> None:
        """Clean up resources and stop threads."""
        self._event_thread_running = False
