import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
import math  # <-- new import

from service.hyprland import HyprlandService

class WorkspaceIndicator(Gtk.Box):
    """
    A widget that displays Hyprland workspaces as a row of indicators.
    
    Dynamically shows workspaces in ranges of 10:
    - 1-10 when active workspace is in that range
    - 11-20 when active workspace is in that range
    - 21-30 when active workspace is in that range
    And so on...
    
    With styling:
    - Active workspace: White background with black text
    - Inactive workspace with windows: White text
    - Empty workspace: Gray text
    """
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)  # Remove spacing here
        
        self.set_name("workspace-indicator")
        # Remove margins from the indicator itself
        
        # Get hyprland service
        self.hyprland = HyprlandService.get_default()
        
        # Current displayed range (start, end)
        self.current_range = (1, 10)
        
        # Create inner box for buttons with gradient
        self.inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.inner_box.set_name("workspace-inner-box")
        self.append(self.inner_box)
        
        # Create workspace indicators for initial range
        self.workspace_buttons = {}
        self.setup_workspace_indicators()
        
        # Connect signals to update UI
        self.hyprland.connect("workspaces-changed", self.update_workspaces)
        self.hyprland.connect("active-workspace-changed", self.update_workspaces)
        
        # Add scroll controller for workspace switching
        scroll_controller = Gtk.EventControllerScroll()
        # Use proper flags enum instead of integer
        scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL | 
            Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self.on_scroll)
        self.add_controller(scroll_controller)
        
        # Store reference for updating CSS
        self.frame = None
        
        # Animation variables
        self.animation_source_id = None
        self.animation_start_time = 0
        self.animation_duration = 500  # 500ms = 0.5 seconds total
        self.animation_start_position = 50  # Default starting position (pixels)
        self.animation_target_position = 50  # Default target position (pixels)
        self.animation_current_position = 50  # Current position during animation
        self.normal_gradient_half_width = 20  # Increased from 10px to 20px for 40px total width
        
        # Animation phase constants
        self.PHASE_DECREASE_MARGINS = 0
        self.PHASE_MOVE_GRADIENT = 1
        self.PHASE_INCREASE_MARGINS = 2
        
        # Multi-phase animation control
        self.animation_phase = self.PHASE_DECREASE_MARGINS
        self.animation_active = False
        self.phase_durations = [100, 250, 150]  # milliseconds for each phase
        self.phase_start_times = [0, 0, 0]  # Will be calculated during animation
        
        # Margin animation variables
        self.previous_active_button = None
        self.current_active_button = None
        self.margin_target_value = 15
        
        # CSS provider for dynamic gradient positioning
        self.css_provider = Gtk.CssProvider()
        
        # Track which workspace button is under the gradient
        self.gradient_button_id = None
        
        # Add gradient width tracking variables
        self.gradient_width_at_phase_change = self.normal_gradient_half_width
        self.previous_workspace = None  # New variable to track previous workspace
        
        # Initial update
        self.update_workspaces()
    
    def get_workspace_range(self, workspace_id):
        """Determine the range (start, end) for a given workspace ID"""
        # Calculate range based on workspace_id
        # For workspace 1-10: range is (1, 10)
        # For workspace 11-20: range is (11, 20)
        # And so on...
        start = ((workspace_id - 1) // 10) * 10 + 1
        end = start + 9
        return (start, end)
    
    def on_scroll(self, controller, dx, dy):
        """Handle scroll events to switch workspaces"""
        # Get current active workspace
        active_workspace = self.hyprland.get_active_workspace()
        if not active_workspace:
            return False
            
        current_id = active_workspace.get("id")
        if current_id is None:
            return False
            
        # Determine direction based on vertical scroll (dy)
        # Scrolling up (negative dy) = previous workspace
        # Scrolling down (positive dy) = next workspace
        if dy < 0:
            # Scroll up, go to previous workspace
            target_id = max(1, current_id - 1)
        else:
            # Scroll down, go to next workspace
            target_id = current_id + 1
        
        # Only switch if the target is different
        if target_id != current_id:
            self.hyprland.switch_to_workspace(target_id)
            
        # Return True to mark the event as handled
        return True
        
    def setup_workspace_indicators(self):
        """Create buttons for the current range of workspaces"""
        # Clear existing buttons from inner_box
        child = self.inner_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.inner_box.remove(child)
            child = next_child
        
        self.workspace_buttons = {}
        
        # Create buttons for current range
        start, end = self.current_range
        for i in range(start, end + 1):
            button = Gtk.Button(label=str(i))
            button.set_size_request(18, 18)  # Smaller button size
            
            # Add CSS classes for styling
            button.add_css_class("workspace-button")
            button.add_css_class(f"workspace-{i}")
            
            # Connect click handler
            button.connect("clicked", self.on_workspace_clicked, i)
            
            # Add to inner box container
            self.inner_box.append(button)
            self.workspace_buttons[i] = button
    
    def calculate_gradient_position(self, active_id):
        """Calculate the position of the gradient based on active workspace in pixels"""
        if not active_id:
            return 50  # Default position in pixels
            
        # For accurate positioning, we need to measure the actual button positions
        # This requires the widget to be realized and have a proper allocation
        if self.inner_box and self.inner_box.get_realized():
            # Find the active button
            active_button = self.workspace_buttons.get(active_id)
            if active_button and active_button.get_realized():
                # Get button's center position in pixels, including its margins
                allocation = active_button.get_allocation()
                
                # Get actual button dimensions including margins
                button_x = allocation.x  # This includes the margin-start
                button_width = allocation.width  # This includes both margins
                button_center_x = button_x + (button_width / 2)
                
                # Return actual pixel position
                return button_center_x
        
        # Fallback calculation if widgets aren't realized yet
        # Just return a default pixel value
        return 50

    def set_gradient_position(self, position, gradient_half_width=None):
        """Immediately set the gradient to a specific position in pixels"""
        if gradient_half_width is None:
            gradient_half_width = self.normal_gradient_half_width
        if self.inner_box:
            # Prepare CSS with new position and gradient half width value in pixels
            css = f"""
                #workspace-inner-box {{
                    --box-position: {position}px;
                    --gradient-half-width: {gradient_half_width}px;
                }}
            """
            
            # Load the CSS into provider
            self.css_provider.load_from_data(css.encode())
            
            # Apply the provider to the display
            display = self.get_display()
            Gtk.StyleContext.add_provider_for_display(
                display,
                self.css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            
            # Update button colors based on gradient position
            self.update_button_colors(position)
    
    def update_button_colors(self, position):
        """Update button colors based on gradient position using pixel measurements"""
        if not self.workspace_buttons:
            return
            
        # Get current gradient half-width in pixels
        gradient_half_width = self.normal_gradient_half_width
        if hasattr(self, 'animation_source_id') and self.animation_source_id:
            # During animation, use current half-width
            css_text = self.css_provider.to_string()
            if '--gradient-half-width:' in css_text:
                try:
                    half_width_text = css_text.split('--gradient-half-width:')[1].split('px')[0].strip()
                    gradient_half_width = float(half_width_text)
                except (IndexError, ValueError):
                    pass
        
        # Define white gradient area in pixels
        x_gradient_start = position - gradient_half_width
        x_gradient_end = position + gradient_half_width
        
        # Update each button's under-gradient state
        for i, button in self.workspace_buttons.items():
            # Remove existing under-gradient class (we'll add it back if needed)
            button.remove_css_class("under-gradient")
            
            # Check if button center is within gradient area - for ALL buttons including active
            if self.inner_box and self.inner_box.get_realized() and button.get_realized():
                # Get button center position in pixels directly
                allocation = button.get_allocation()
                button_x = allocation.x
                button_width = allocation.width
                button_center_x = button_x + (button_width / 2)
                
                # Check if button center is within gradient area
                if x_gradient_start <= button_center_x <= x_gradient_end:
                    button.add_css_class("under-gradient")
    
    def update_workspaces(self, *args):
        """Update workspace indicators based on Hyprland state"""
        workspaces = self.hyprland.get_workspaces()
        active_workspace = self.hyprland.get_active_workspace()
        active_id = active_workspace.get("id") if active_workspace else None
        
        # Log only the current workspace
        if active_id:
            print(f"Current workspace: {active_id}")
        
        # Check if we need to change the displayed range
        if active_id:
            new_range = self.get_workspace_range(active_id)
            if new_range != self.current_range:
                self.current_range = new_range
                self.setup_workspace_indicators()
                
                # For range changes, immediately set active button without animation
                for i, button in self.workspace_buttons.items():
                    # Remove active class from all
                    button.remove_css_class("active")
                    # Reset margins
                    button.set_margin_start(0)
                    button.set_margin_end(0)
                    
                    # Set active state and margins for current active
                    if i == active_id:
                        button.add_css_class("active")
                        button.set_margin_start(self.margin_target_value)
                        button.set_margin_end(self.margin_target_value)
                
                # Update previous workspace when range changes
                self.previous_workspace = active_id
                return
        
        # Create lookup dict for workspaces with window counts
        workspace_dict = {ws.get("id"): ws.get("windows", 0) for ws in workspaces}
        
        # Update each workspace button's has-windows state
        for i, button in self.workspace_buttons.items():
            # Update active state without changing margins yet
            if i == active_id:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")
                
            # Set has-windows state
            button.remove_css_class("has-windows")
            if workspace_dict.get(i, 0) > 0:
                button.add_css_class("has-windows")
        
        # Only run animation if the workspace changed
        if self.previous_workspace is None or self.previous_workspace != active_id:
            self.previous_workspace = active_id
            GLib.timeout_add(20, self.start_animation_sequence, active_id)
    
    def start_animation_sequence(self, active_id):
        """Start multi-phase animation sequence for workspace transition"""
        if self.frame and active_id:
            new_active_button = self.workspace_buttons.get(active_id)
            
            # Find previous active button (the one with margins)
            previous_active_button = None
            for btn in self.workspace_buttons.values():
                if btn != new_active_button and (btn.get_margin_start() > 0 or btn.get_margin_end() > 0):
                    previous_active_button = btn
                    break
            
            # If there's no previous active button or it's the same as new one, skip first phase
            skip_first_phase = (previous_active_button is None or previous_active_button == new_active_button)
            
            if new_active_button and new_active_button.get_realized():
                # Cancel any existing animation
                if self.animation_source_id is not None:
                    GLib.source_remove(self.animation_source_id)
                    self.animation_source_id = None
                
                # Set up animation parameters
                self.animation_active = True
                self.animation_start_time = GLib.get_monotonic_time()
                
                # Gradient animation parameters
                current_position = self.animation_current_position
                target_position = self.calculate_gradient_position(active_id)
                self.animation_start_position = current_position
                self.animation_target_position = target_position
                
                # Button references for animation
                self.previous_active_button = previous_active_button
                self.current_active_button = new_active_button
                
                # Calculate phase start times
                if skip_first_phase:
                    # Skip margin decrease phase
                    self.animation_phase = self.PHASE_MOVE_GRADIENT
                    self.phase_start_times = [0, 0, self.phase_durations[0] + self.phase_durations[1]]
                else:
                    # Include all phases
                    self.animation_phase = self.PHASE_DECREASE_MARGINS
                    self.phase_start_times = [0, self.phase_durations[0], self.phase_durations[0] + self.phase_durations[1]]
                
                # Start the multi-phase animation
                self.animation_source_id = GLib.timeout_add(16, self.multi_phase_animation_step)
            else:
                # Button not realized yet, try again shortly
                GLib.timeout_add(20, self.start_animation_sequence, active_id)
                return False
        
        return False  # Don't repeat
    
    def multi_phase_animation_step(self):
        """Handle multi-phase animation with margins and gradient movement"""
        if not self.frame or not self.animation_active:
            self.animation_source_id = None
            return False
        
        current_time = GLib.get_monotonic_time()
        elapsed_total = (current_time - self.animation_start_time) / 1000  # ms
        
        if elapsed_total >= sum(self.phase_durations):
            self.finish_animation()
            return False

        # Track phase transitions
        previous_phase = self.animation_phase
        
        if self.animation_phase == self.PHASE_MOVE_GRADIENT and self.current_active_button and self.current_active_button.get_realized():
            allocation = self.current_active_button.get_allocation()
            btn_start = allocation.x
            btn_end = allocation.x + allocation.width
            if btn_start <= self.animation_current_position <= btn_end:
                # Store current gradient width before phase change
                # This will be used to smoothly transition the width back to normal
                distance = abs(self.animation_target_position - self.animation_start_position)
                overall_progress = min((elapsed_total - self.phase_start_times[0]) / (self.phase_durations[0] + self.phase_durations[1]), 1.0)
                peak_width = self.normal_gradient_half_width + 0.4 * distance
                if overall_progress <= 0.5:
                    self.gradient_width_at_phase_change = self.normal_gradient_half_width + (peak_width - self.normal_gradient_half_width) * (overall_progress / 0.5)
                else:
                    self.gradient_width_at_phase_change = peak_width - (peak_width - self.normal_gradient_half_width) * ((overall_progress - 0.5) / 0.5)
                
                # Change phase
                self.animation_phase = self.PHASE_INCREASE_MARGINS
                self.phase_start_times[self.PHASE_INCREASE_MARGINS] = elapsed_total
                self.phase_durations[self.PHASE_INCREASE_MARGINS] = max(500 - elapsed_total, 50)
        
        if self.animation_phase == self.PHASE_DECREASE_MARGINS and elapsed_total >= self.phase_start_times[1]:
            self.animation_phase = self.PHASE_MOVE_GRADIENT
        
        # Detect if phase just changed
        phase_changed = previous_phase != self.animation_phase
        
        # Calculate progress for current phase
        phase_start_time = self.phase_start_times[self.animation_phase]
        phase_duration = self.phase_durations[self.animation_phase]
        phase_elapsed = elapsed_total - phase_start_time
        phase_progress = min(phase_elapsed / phase_duration, 1.0)
        eased_progress = 0.5 * (1 - math.cos(math.pi * phase_progress))
        
        if self.animation_phase == self.PHASE_DECREASE_MARGINS:
            if self.previous_active_button:
                start_margin = self.margin_target_value
                current_margin = start_margin * (1 - eased_progress)
                margin_value = int(round(current_margin))
                self.previous_active_button.set_margin_start(margin_value)
                self.previous_active_button.set_margin_end(margin_value)
        
        elif self.animation_phase == self.PHASE_MOVE_GRADIENT:
            overall_progress = min((elapsed_total - self.phase_start_times[0]) / (self.phase_durations[0] + self.phase_durations[1]), 1.0)
            overall_eased = 0.5 * (1 - math.cos(math.pi * overall_progress))
            
            # Position animation
            self.animation_current_position = (
                self.animation_start_position +
                (self.animation_target_position - self.animation_start_position) * overall_eased
            )
            
            # Width animation
            distance = abs(self.animation_target_position - self.animation_start_position)
            peak_width = self.normal_gradient_half_width + 0.4 * distance
            if overall_progress <= 0.5:
                current_half_width = self.normal_gradient_half_width + (peak_width - self.normal_gradient_half_width) * (overall_progress / 0.5)
            else:
                current_half_width = peak_width - (peak_width - self.normal_gradient_half_width) * ((overall_progress - 0.5) / 0.5)
            
            self.set_gradient_position(self.animation_current_position, current_half_width)
        
        elif self.animation_phase == self.PHASE_INCREASE_MARGINS:
            if self.current_active_button and self.current_active_button.get_realized():
                # Position animation - follow the expanding button center
                allocation = self.current_active_button.get_allocation()
                btn_center = allocation.x + (allocation.width / 2)
                self.animation_current_position = (
                    self.animation_current_position * 0.7 + btn_center * 0.3
                )
                
                # Margin animation
                current_margin = self.margin_target_value * eased_progress
                margin_value = int(round(current_margin))
                self.current_active_button.set_margin_start(margin_value)
                self.current_active_button.set_margin_end(margin_value)
                
                # Gradient width animation - gradually return to normal width
                # This ensures continuous width animation from phase 2 to phase 3
                current_half_width = self.gradient_width_at_phase_change + (self.normal_gradient_half_width - self.gradient_width_at_phase_change) * eased_progress
                
                self.set_gradient_position(self.animation_current_position, current_half_width)
        
        return True
    
    def finish_animation(self):
        """Clean up at the end of animation"""
        # Make sure final state is correct
        if self.current_active_button:
            self.current_active_button.set_margin_start(self.margin_target_value)
            self.current_active_button.set_margin_end(self.margin_target_value)
            
            # Ensure gradient is centered on the button
            if self.current_active_button.get_realized():
                allocation = self.current_active_button.get_allocation()
                final_pos = allocation.x + (allocation.width / 2)
                self.animation_current_position = final_pos
                self.set_gradient_position(final_pos)
        
        # Reset animation state
        self.animation_active = False
        self.animation_source_id = None
        return False
    
    def on_workspace_clicked(self, button, workspace_id):
        """Switch to the clicked workspace"""
        self.hyprland.switch_to_workspace(workspace_id)


class WorkspaceBar(Gtk.Box):
    """A container for the workspace indicator with styling"""
    
    def __init__(self, application=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        # Store application reference if provided
        self.application = application
        
        self.set_name("workspace-bar")
        self.add_css_class("panel")
        self.set_valign(Gtk.Align.CENTER)  # Center this bar vertically
        
        # Create frame for the workspace indicator
        frame = Gtk.Frame(name="workspace-frame")
        frame.set_margin_start(2)  # Reduced margins
        frame.set_margin_end(2)
        frame.set_margin_top(2)
        frame.set_margin_bottom(2)
        frame.set_valign(Gtk.Align.CENTER)  # Center frame vertically
        
        # Add workspace indicator to frame
        self.workspace_indicator = WorkspaceIndicator()
        self.workspace_indicator.frame = frame  # Store frame reference in the indicator
        self.workspace_indicator.set_valign(Gtk.Align.CENTER)  # Center indicator vertically
        frame.set_child(self.workspace_indicator)
        
        # Add frame to this container
        self.append(frame)
        
        # Also add scroll handling to the bar itself
        scroll_controller = Gtk.EventControllerScroll()
        # Use proper flags enum instead of integer
        scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL | 
            Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self.workspace_indicator.on_scroll)
        self.add_controller(scroll_controller)
        
        # Trigger initial gradient position update
        self.workspace_indicator.update_workspaces()

# For testing the module individually
if __name__ == "__main__":
    def on_activate(app):
        window = Gtk.ApplicationWindow(application=app, title="Workspace Test")
        window.set_default_size(600, 100)
        
        # Create workspace bar
        workspace_bar = WorkspaceBar()
        
        # Add to window with some margin
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.append(workspace_bar)
        
        window.set_child(box)
        window.present()
    
    # Create and run app
    app = Gtk.Application(application_id="com.example.workspace")
    app.connect("activate", on_activate)
    app.run(None)