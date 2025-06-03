import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
import math

from service.hyprland import HyprlandService

class WorkspaceIndicator(Gtk.Box):
    """
    A widget that displays Hyprland workspaces as a row of indicators.
    
    ### Features:
    - Displays workspaces in ranges of 10 (e.g., 1-10, 11-20, 21-30) based on the active workspace.
    - Styling:
      - **Active workspace**: White background with black text.
      - **Inactive with windows**: White text.
      - **Empty workspace**: Gray text.
    - Maintains constant panel width during workspace switches by adjusting button margins.
    - Smooth gradient animation follows the active workspace.
    """
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_name("workspace-indicator")
        
        # Initialize Hyprland service
        self.hyprland = HyprlandService.get_default()
        
        # Current displayed range
        self.current_range = (1, 10)
        
        # Inner box for buttons with gradient
        self.inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.inner_box.set_name("workspace-inner-box")
        self.append(self.inner_box)
        
        # Workspace buttons dictionary
        self.workspace_buttons = {}
        
        # Animation variables
        self.frame = None
        self.animation_source_id = None
        self.animation_start_time = 0
        self.animation_duration = 400  # ms
        self.animation_start_position = 50  # px
        self.animation_target_position = 50  # px
        self.animation_current_position = 50  # px
        self.normal_gradient_half_width = 20  # px
        
        # Animation phases
        self.PHASE_MOVE_GRADIENT_AND_ADJUST_MARGINS = 0
        self.PHASE_FINALIZE = 1
        self.animation_phase = self.PHASE_MOVE_GRADIENT_AND_ADJUST_MARGINS
        self.animation_active = False
        self.phase_durations = [300, 100]  # ms per phase
        self.phase_start_times = [0, 0]
        
        # Margin animation
        self.previous_active_button = None
        self.current_active_button = None
        self.margin_target_value = 15  # px
        self.animated_prev_buttons = []
        self.animated_prev_margins = {}
        self.current_active_margin_initial = 0
        
        # CSS provider for gradient
        self.css_provider = Gtk.CssProvider()
        self.gradient_button_id = None
        self.gradient_width_at_phase_change = self.normal_gradient_half_width
        self.phase_finalize_start_position = 0
        self.previous_workspace = None
        self.is_initialized = False
        
        # Focus controller
        controller = Gtk.EventControllerFocus.new()
        self.add_controller(controller)
        
        # Scroll controller for workspace switching
        scroll_controller = Gtk.EventControllerScroll()
        scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL | 
            Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self.on_scroll)
        self.add_controller(scroll_controller)
        
        # Initialize workspaces and positioning
        self.initialize_workspaces()
        
        # Connect Hyprland signals after initialization
        self.hyprland.connect("workspaces-changed", self.update_workspaces)
        self.hyprland.connect("active-workspace-changed", self.update_workspaces)
        
        # Map event for ensuring proper initialization
        self.connect("map", self.on_map_event)
        self.connect("realize", self.on_realize_event)
    
    def initialize_workspaces(self):
        """Initialize workspaces based on current Hyprland state."""
        # Get current active workspace to determine initial range
        active_workspace = self.hyprland.get_active_workspace()
        active_id = active_workspace.get("id") if active_workspace else 1
        
        # Set current range based on active workspace
        self.current_range = self.get_workspace_range(active_id)
        self.previous_workspace = active_id
        
        # Setup workspace indicators
        self.setup_workspace_indicators()
        
        # Update workspace states
        self.update_workspace_states()
    
    def get_workspace_range(self, workspace_id):
        """Determine the range (start, end) for a given workspace ID."""
        start = ((workspace_id - 1) // 10) * 10 + 1
        end = start + 9
        return (start, end)
    
    def on_scroll(self, controller, dx, dy):
        """Handle scroll events to switch workspaces."""
        active_workspace = self.hyprland.get_active_workspace()
        if not active_workspace or active_workspace.get("id") is None:
            return False
            
        current_id = active_workspace.get("id")
        target_id = current_id - 1 if dy < 0 else current_id + 1
        target_id = max(1, target_id)
        
        if target_id != current_id:
            self.hyprland.switch_to_workspace(target_id)
        return True
    
    def setup_workspace_indicators(self):
        """Create buttons for the current range of workspaces."""
        # Clear existing buttons
        child = self.inner_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.inner_box.remove(child)
            child = next_child
        
        self.workspace_buttons = {}
        start, end = self.current_range
        for i in range(start, end + 1):
            button = Gtk.Button(label=str(i))
            button.set_size_request(18, 18)
            button.workspace_id = i
            button.add_css_class("workspace-button")
            button.add_css_class(f"workspace-{i}")
            button.connect("clicked", self.on_workspace_clicked, i)
            self.inner_box.append(button)
            self.workspace_buttons[i] = button
    
    def update_workspace_states(self):
        """Update workspace button states without animations."""
        workspaces = self.hyprland.get_workspaces()
        active_workspace = self.hyprland.get_active_workspace()
        active_id = active_workspace.get("id") if active_workspace else None
        
        workspace_dict = {ws.get("id"): ws.get("windows", 0) for ws in workspaces}
        
        for i, button in self.workspace_buttons.items():
            # Clear all classes
            button.remove_css_class("active")
            button.remove_css_class("empty")
            button.remove_css_class("has-windows")
            button.remove_css_class("under-gradient")
            
            # Reset margins
            button.set_margin_start(0)
            button.set_margin_end(0)
            
            has_windows = workspace_dict.get(i, 0) > 0
            
            if i == active_id:
                button.set_label(str(i))
                button.add_css_class("active")
                button.set_margin_start(self.margin_target_value)
                button.set_margin_end(self.margin_target_value)
                self.current_active_button = button
            elif has_windows:
                button.set_label(str(i))
                button.add_css_class("has-windows")
            else:
                button.set_label("•")
                button.add_css_class("empty")
    
    def calculate_gradient_position(self, active_id):
        """Calculate gradient position in pixels based on active workspace."""
        if not active_id or not self.inner_box.get_realized():
            return 50
            
        active_button = self.workspace_buttons.get(active_id)
        if active_button and active_button.get_realized():
            allocation = active_button.get_allocation()
            return allocation.x + (allocation.width / 2)
        return 50

    def set_gradient_position(self, position, gradient_half_width=None):
        """Set gradient position immediately."""
        if gradient_half_width is None:
            gradient_half_width = self.normal_gradient_half_width
        css = f"""
            #workspace-inner-box {{
                --box-position: {position}px;
                --gradient-half-width: {gradient_half_width}px;
            }}
        """
        self.css_provider.load_from_data(css.encode())
        display = self.get_display()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                self.css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        self.update_button_colors(position)
    
    def update_button_colors(self, position):
        """Update button colors based on gradient position."""
        if not self.workspace_buttons or not self.inner_box.get_realized():
            return
            
        gradient_half_width = self.normal_gradient_half_width
        css_text = self.css_provider.to_string()
        if '--gradient-half-width:' in css_text:
            try:
                gradient_half_width = float(css_text.split('--gradient-half-width:')[1].split('px')[0].strip())
            except (IndexError, ValueError):
                pass
        
        x_gradient_start = position - gradient_half_width
        x_gradient_end = position + gradient_half_width
        
        for i, button in self.workspace_buttons.items():
            button.remove_css_class("under-gradient")
            if button.get_realized():
                allocation = button.get_allocation()
                button_center_x = allocation.x + (allocation.width / 2)
                if x_gradient_start <= button_center_x <= x_gradient_end:
                    button.add_css_class("under-gradient")
    
    def ensure_initial_positioning(self):
        """Ensure the gradient is positioned correctly on the active workspace."""
        if self.is_initialized:
            return False
            
        active_workspace = self.hyprland.get_active_workspace()
        active_id = active_workspace.get("id") if active_workspace else None
        
        if active_id and active_id in self.workspace_buttons:
            button = self.workspace_buttons[active_id]
            if button.get_realized() and button.get_allocation():
                allocation = button.get_allocation()
                if allocation.width > 0 and allocation.height > 0:
                    center_x = allocation.x + (allocation.width / 2)
                    self.animation_current_position = center_x
                    self.animation_start_position = center_x
                    self.animation_target_position = center_x
                    self.set_gradient_position(center_x)
                    self.is_initialized = True
                    print(f"Initial gradient positioned at {center_x}px for workspace {active_id}")
                    return False
        
        # If not ready yet, try again
        return True
    
    def on_realize_event(self, widget):
        """Handle realize event."""
        GLib.idle_add(self.ensure_initial_positioning)
        return False
    
    def on_map_event(self, widget):
        """Handle map event for initial gradient positioning."""
        GLib.idle_add(self.ensure_initial_positioning)
        return False
    
    def update_workspaces(self, *args):
        """Update workspace indicators based on Hyprland state."""
        workspaces = self.hyprland.get_workspaces()
        active_workspace = self.hyprland.get_active_workspace()
        active_id = active_workspace.get("id") if active_workspace else None
        
        if active_id:
            new_range = self.get_workspace_range(active_id)
            if new_range != self.current_range:
                # Workspace range changed, rebuild indicators
                self.current_range = new_range
                self.setup_workspace_indicators()
                self.update_workspace_states()
                # Reset initialization flag and reposition
                self.is_initialized = False
                GLib.idle_add(self.ensure_initial_positioning)
                self.previous_workspace = active_id
                return

        # Update workspace states
        workspace_dict = {ws.get("id"): ws.get("windows", 0) for ws in workspaces}
        for i, button in self.workspace_buttons.items():
            has_windows = workspace_dict.get(i, 0) > 0
            if i == active_id:
                button.set_label(str(i))
                button.add_css_class("active")
                button.remove_css_class("empty")
                button.remove_css_class("has-windows")
            else:
                if has_windows:
                    button.set_label(str(i))
                    button.add_css_class("has-windows")
                    button.remove_css_class("active")
                    button.remove_css_class("empty")
                else:
                    button.set_label("•")
                    button.add_css_class("empty")
                    button.remove_css_class("active")
                    button.remove_css_class("has-windows")
        
        # Handle workspace change animation
        if self.previous_workspace != active_id:
            self.previous_workspace = active_id
            if self.is_initialized:
                GLib.idle_add(self.start_animation_sequence, active_id)
            else:
                # If not initialized yet, just position directly
                GLib.idle_add(self.ensure_initial_positioning)
    
    def calculate_final_gradient_position(self, active_id):
        """Calculate the final gradient position after margins are applied."""
        if active_id not in self.workspace_buttons:
            return 0
        active_button = self.workspace_buttons[active_id]
        sum_prev_widths = 0
        current = self.inner_box.get_first_child()
        while current and current != active_button:
            allocation = current.get_allocation()
            if allocation:
                sum_prev_widths += allocation.width
            current = current.get_next_sibling()
        final_x = sum_prev_widths + self.margin_target_value
        active_width = active_button.get_allocation().width if active_button.get_allocation() else 0
        final_center = final_x + active_width / 2
        return final_center
    
    def start_animation_sequence(self, active_id):
        """Start multi-phase animation for workspace transition."""
        if self.frame and active_id:
            new_active_button = self.workspace_buttons.get(active_id)
            if new_active_button and new_active_button.get_realized():
                if self.animation_source_id:
                    GLib.source_remove(self.animation_source_id)
                
                self.animation_active = True
                self.animation_start_time = GLib.get_monotonic_time()
                self.animation_start_position = self.animation_current_position
                self.animation_target_position = self.calculate_final_gradient_position(active_id)
                self.current_active_button = new_active_button
                
                self.animated_prev_buttons = [
                    btn for btn in self.workspace_buttons.values()
                    if btn != new_active_button and (btn.get_margin_start() > 0 or btn.get_margin_end() > 0)
                ]
                self.animated_prev_margins = {btn: btn.get_margin_start() for btn in self.animated_prev_buttons}
                self.current_active_margin_initial = new_active_button.get_margin_start()
                
                self.animation_phase = self.PHASE_MOVE_GRADIENT_AND_ADJUST_MARGINS
                self.phase_start_times = [0, self.phase_durations[0]]
                self.animation_source_id = GLib.idle_add(self.multi_phase_animation_step)
            else:
                GLib.idle_add(self.start_animation_sequence, active_id)
                return False
        return False

    def multi_phase_animation_step(self):
        """Handle multi-phase animation with margin adjustments."""
        if not self.frame or not self.animation_active:
            self.animation_source_id = None
            return False
        
        current_time = GLib.get_monotonic_time()
        elapsed_total = (current_time - self.animation_start_time) / 1000
        
        if elapsed_total >= sum(self.phase_durations):
            self.finish_animation()
            return False

        if self.animation_phase == self.PHASE_MOVE_GRADIENT_AND_ADJUST_MARGINS and elapsed_total >= self.phase_start_times[1]:
            self.phase_finalize_start_position = self.animation_current_position
            distance = abs(self.animation_target_position - self.animation_start_position)
            peak_width = self.normal_gradient_half_width + 0.4 * distance
            self.gradient_width_at_phase_change = peak_width - (peak_width - self.normal_gradient_half_width) * ((1.0 - 0.5) / 0.5)
            
            self.animation_phase = self.PHASE_FINALIZE
            phase_start_time = self.phase_start_times[self.animation_phase]
            phase_duration = self.phase_durations[self.animation_phase]
            phase_elapsed = elapsed_total - phase_start_time
            phase_progress = min(phase_elapsed / phase_duration, 1.0)
            eased_progress = 0.5 * (1 - math.cos(math.pi * phase_progress))
        else:
            phase_start_time = self.phase_start_times[self.animation_phase]
            phase_duration = self.phase_durations[self.animation_phase]
            phase_elapsed = elapsed_total - phase_start_time
            phase_progress = min(phase_elapsed / phase_duration, 1.0)
            eased_progress = 0.5 * (1 - math.cos(math.pi * phase_progress))

        if self.animation_phase == self.PHASE_MOVE_GRADIENT_AND_ADJUST_MARGINS:
            self.animation_current_position = (
                self.animation_start_position +
                (self.animation_target_position - self.animation_start_position) * eased_progress
            )
            distance = abs(self.animation_target_position - self.animation_start_position)
            peak_width = self.normal_gradient_half_width + 0.4 * distance
            current_half_width = (
                self.normal_gradient_half_width + (peak_width - self.normal_gradient_half_width) * (phase_progress / 0.5)
                if phase_progress <= 0.5
                else peak_width - (peak_width - self.normal_gradient_half_width) * ((phase_progress - 0.5) / 0.5)
            )
            self.set_gradient_position(self.animation_current_position, current_half_width)
            
            sum_decreasing = 0
            for btn in self.animated_prev_buttons:
                initial_margin = self.animated_prev_margins.get(btn, 0)
                new_margin = int(round(initial_margin * (1 - eased_progress)))
                btn.set_margin_start(new_margin)
                btn.set_margin_end(new_margin)
                sum_decreasing += 2 * new_margin
            
            if self.current_active_button:
                target_total_margin = 2 * self.margin_target_value
                new_margin_active = int(round((target_total_margin - sum_decreasing) / 2))
                new_margin_active = max(0, min(new_margin_active, self.margin_target_value))
                self.current_active_button.set_margin_start(new_margin_active)
                self.current_active_button.set_margin_end(new_margin_active)
                self.current_active_button.set_label(str(self.current_active_button.workspace_id))
                
        elif self.animation_phase == self.PHASE_FINALIZE:
            if self.current_active_button and self.current_active_button.get_realized():
                allocation = self.current_active_button.get_allocation()
                btn_center = allocation.x + (allocation.width / 2)
                self.animation_current_position = (
                    self.phase_finalize_start_position +
                    (btn_center - self.phase_finalize_start_position) * eased_progress
                )
                final_margin = int(round(self.margin_target_value))
                self.current_active_button.set_margin_start(final_margin)
                self.current_active_button.set_margin_end(final_margin)
                current_half_width = self.gradient_width_at_phase_change + (self.normal_gradient_half_width - self.gradient_width_at_phase_change) * eased_progress
                self.set_gradient_position(self.animation_current_position, current_half_width)
                for btn in self.animated_prev_buttons:
                    btn.set_margin_start(0)
                    btn.set_margin_end(0)
        
        return True

    def finish_animation(self):
        """Clean up after animation."""
        if self.current_active_button:
            self.current_active_button.set_margin_start(self.margin_target_value)
            self.current_active_button.set_margin_end(self.margin_target_value)
            if self.current_active_button.get_realized():
                allocation = self.current_active_button.get_allocation()
                final_pos = allocation.x + (allocation.width / 2)
                self.animation_current_position = final_pos
                self.set_gradient_position(final_pos)
        
        for btn in self.animated_prev_buttons:
            btn.set_margin_start(0)
            btn.set_margin_end(0)
        
        self.animation_active = False
        self.animation_source_id = None

        # Force update all non-active, empty workspaces to show "•"
        workspace_dict = {ws.get("id"): ws.get("windows", 0) for ws in self.hyprland.get_workspaces()}
        for i, button in self.workspace_buttons.items():
            if not button.has_css_class("active") and not (workspace_dict.get(i, 0) > 0):
                button.set_label("•")
        
        return False
    
    def on_workspace_clicked(self, button, workspace_id):
        """Switch to clicked workspace."""
        self.hyprland.switch_to_workspace(workspace_id)


class WorkspaceBar(Gtk.Box):
    """A container for the workspace indicator with styling."""
    
    def __init__(self, application=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.application = application
        self.set_name("workspace-bar")
        self.add_css_class("panel")
        self.set_valign(Gtk.Align.CENTER)
        
        # Frame for workspace indicator
        frame = Gtk.Frame(name="workspace-frame")
        frame.set_valign(Gtk.Align.CENTER)
        frame.vexpand = True
        frame.set_size_request(-1, 40)
        
        # Add workspace indicator
        self.workspace_indicator = WorkspaceIndicator()
        self.workspace_indicator.frame = frame
        self.workspace_indicator.set_valign(Gtk.Align.CENTER)
        frame.set_child(self.workspace_indicator)
        self.append(frame)
        
        # Scroll controller
        scroll_controller = Gtk.EventControllerScroll()
        scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL | 
            Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self.workspace_indicator.on_scroll)
        self.add_controller(scroll_controller)


# For standalone testing
if __name__ == "__main__":
    def on_activate(app):
        window = Gtk.ApplicationWindow(application=app, title="Workspace Test")
        window.set_default_size(600, 100)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        workspace_bar = WorkspaceBar()
        box.append(workspace_bar)
        window.set_child(box)
        window.present()
    
    app = Gtk.Application(application_id="com.example.workspace")
    app.connect("activate", on_activate)
    app.run(None)