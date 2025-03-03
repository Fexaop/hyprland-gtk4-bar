import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

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
        self.animation_duration = 250  # 250ms = 0.25 seconds
        self.animation_start_position = 17  # Default starting position
        self.animation_target_position = 17  # Default target position
        self.animation_current_position = 17  # Current position during animation
        self.normal_gradient_half_width = 10  # Default half width for gradient
        
        # CSS provider for dynamic gradient positioning
        self.css_provider = Gtk.CssProvider()
        
        # Track which workspace button is under the gradient
        self.gradient_button_id = None
        
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
            print(f"Scrolling to workspace {target_id}")
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
        """Calculate the position of the gradient based on active workspace with margin compensation"""
        if not active_id:
            return 17  # Default position (%)
            
        start, end = self.current_range
        
        # For accurate positioning, we need to measure the actual button positions
        # This requires the widget to be realized and have a proper allocation
        if self.inner_box and self.inner_box.get_realized():
            # Find the active button
            active_button = self.workspace_buttons.get(active_id)
            if active_button and active_button.get_realized():
                # Get the button's allocation relative to the inner_box
                inner_box_width = self.inner_box.get_width()
                if inner_box_width > 0:
                    # Get button's center position in pixels
                    button_x = active_button.get_allocation().x
                    button_width = active_button.get_allocation().width
                    button_center_x = button_x + (button_width / 2)
                    
                    # Convert to percentage of inner_box width
                    position = (button_center_x / inner_box_width) * 100
                    return position
        
        # Fallback calculation if widgets aren't realized yet
        num_buttons = end - start + 1
        button_idx = active_id - start
        
        # Base width of each segment
        segment_width = 100 / num_buttons
        
        # Position without margins would be at the center of the segment
        base_position = (button_idx + 0.5) * segment_width
        
        # Margin effect depends on inner_box width
        # If we can't measure it yet, make an educated guess
        if self.inner_box and self.inner_box.get_realized() and self.inner_box.get_width() > 0:
            # Calculate how much 30px (15px each side) shifts the percentage
            inner_box_width = self.inner_box.get_width()
            margin_percent = (30 / inner_box_width) * 100
            
            # For buttons after the active one, they get pushed right
            # So we need to adjust the gradient position
            adjusted_position = base_position
            
            return adjusted_position
        
        # If we can't measure yet, return base position
        return base_position

    def animate_gradient(self, start_position, target_position):
        """Start gradient position animation"""
        # Cancel any existing animation
        if self.animation_source_id is not None:
            GLib.source_remove(self.animation_source_id)
            self.animation_source_id = None
            
        # Set animation parameters
        self.animation_start_position = start_position
        self.animation_target_position = target_position
        self.animation_current_position = start_position
        self.animation_start_time = GLib.get_monotonic_time()  # Microseconds
        
        # Start animation timer - aim for 60fps (16.67ms intervals)
        self.animation_source_id = GLib.timeout_add(16, self.animation_step)
    
    def animation_step(self):
        """Update animation for one step"""
        if not self.frame:
            self.animation_source_id = None
            return False
            
        # Calculate elapsed time in milliseconds
        current_time = GLib.get_monotonic_time()
        elapsed = (current_time - self.animation_start_time) / 1000  # Convert to milliseconds
        
        # Calculate progress (0.0 to 1.0)
        progress = min(elapsed / self.animation_duration, 1.0)
        
        # Use easeInOutCubic easing function for smoother animation
        if progress < 0.5:
            progress = 4 * progress * progress * progress
        else:
            progress = 1 - pow(-2 * progress + 2, 3) / 2
            
        # Calculate current position
        self.animation_current_position = (
            self.animation_start_position +
            (self.animation_target_position - self.animation_start_position) * progress
        )
        
        # Calculate temporary gradient half width in a triangular animation:
        distance = abs(self.animation_target_position - self.animation_start_position)
        peak_width = self.normal_gradient_half_width + 0.5 * distance
        if progress <= 0.5:
            current_half_width = self.normal_gradient_half_width + (peak_width - self.normal_gradient_half_width) * (progress / 0.5)
        else:
            current_half_width = peak_width - (peak_width - self.normal_gradient_half_width) * ((progress - 0.5) / 0.5)
        
        # Update CSS with new position
        self.set_gradient_position(self.animation_current_position, current_half_width)
        
        # Continue animation if not finished
        if progress < 1.0:
            return True
            
        # Animation complete
        self.animation_source_id = None
        return False
    
    def set_gradient_position(self, position, gradient_half_width=None):
        """Immediately set the gradient to a specific position"""
        if gradient_half_width is None:
            gradient_half_width = self.normal_gradient_half_width
        if self.inner_box:
            # Prepare CSS with new position and gradient half width value
            css = f"""
                #workspace-inner-box {{
                    --box-position: {position}%;
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
            
            # Log the coordinate system after CSS update
            self.log_coordinate_system()
    
    def log_coordinate_system(self):
        """Log the coordinate system information"""
        # Assume inner_box coordinate system width is 100 units, starting at x=0.
        x0 = 0
        # White gradient spans from x1 to x2 using current gradient position (position in %)
        x1 = self.animation_current_position - 5
        x2 = self.animation_current_position + 5
        print(f"[Coordination] Workspace inner box coordinate system: x0 = {x0}")
        print(f"[Coordination] White gradient area: from x = {x1} to x = {x2}")
        
        # For each workspace button (from the current range), calculate its area.
        start, end = self.current_range
        num_buttons = end - start + 1
        segment_width = 100 / num_buttons
        for i in range(start, end + 1):
            idx = i - start  # 0-indexed
            area_start = segment_width * idx
            area_end = segment_width * (idx + 1)
            print(f"[Coordination] Workspace {i} button area: from x = {area_start:.2f} to x = {area_end:.2f}")
    
    def update_button_colors(self, position):
        """Update button colors based on gradient position using center point check"""
        if not self.workspace_buttons:
            return
            
        # Get current gradient half-width
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
        
        # Convert to percentage for position calculations
        gradient_half_width_pct = 5  # Default fallback
        if self.inner_box and self.inner_box.get_realized() and self.inner_box.get_width() > 0:
            gradient_half_width_pct = (gradient_half_width / self.inner_box.get_width()) * 100
        
        # Define white gradient area
        x_gradient_start = position - gradient_half_width_pct
        x_gradient_end = position + gradient_half_width_pct
        
        # Update each button's under-gradient state
        for i, button in self.workspace_buttons.items():
            # Default: button is not under gradient
            button.remove_css_class("under-gradient")
            
            if button.has_css_class("active"):
                # Active button is always under the gradient (that's where we center it)
                button.add_css_class("under-gradient")
            else:
                # For non-active buttons, check if their center is in the gradient area
                # We need to measure their actual position
                if self.inner_box and self.inner_box.get_realized() and button.get_realized():
                    inner_box_width = self.inner_box.get_width()
                    if inner_box_width > 0:
                        # Get button center position in percentage
                        button_x = button.get_allocation().x
                        button_width = button.get_allocation().width
                        button_center_pct = ((button_x + button_width/2) / inner_box_width) * 100
                        
                        # Check if button center is within gradient area
                        if x_gradient_start <= button_center_pct <= x_gradient_end:
                            button.add_css_class("under-gradient")
    
    def update_gradient_position(self, active_id):
        """Update the gradient position with animation"""
        if self.frame:
            # Calculate target position
            target_position = self.calculate_gradient_position(active_id)
            
            # Get current position (use target if first run)
            current_position = self.animation_current_position
            
            # Start animation from current to target
            self.animate_gradient(current_position, target_position)
    
    def update_workspaces(self, *args):
        """Update workspace indicators based on Hyprland state"""
        workspaces = self.hyprland.get_workspaces()
        active_workspace = self.hyprland.get_active_workspace()
        active_id = active_workspace.get("id") if active_workspace else None
        
        # Check if we need to change the displayed range
        if active_id:
            new_range = self.get_workspace_range(active_id)
            if new_range != self.current_range:
                self.current_range = new_range
                self.setup_workspace_indicators()
        
        # Create lookup dict for workspaces with window counts
        workspace_dict = {ws.get("id"): ws.get("windows", 0) for ws in workspaces}
        
        # Update each workspace button
        active_button = None
        for i, button in self.workspace_buttons.items():
            # Remove existing state classes
            button.remove_css_class("active")
            button.remove_css_class("has-windows")
            button.remove_css_class("under-gradient")
            
            # Reset any margins
            button.set_margin_start(0)
            button.set_margin_end(0)
            
            # Set active state
            if i == active_id:
                button.add_css_class("active")
                button.set_margin_start(15)
                button.set_margin_end(15)
                active_button = button
            
            # Set has-windows state
            if workspace_dict.get(i, 0) > 0:
                button.add_css_class("has-windows")
        
        # Wait a bit for the margins to be applied before calculating positions
        GLib.timeout_add(50, self.update_gradient_position_with_margins, active_id)
        
        # Update button colors will be called by the gradient position update
    
    def update_gradient_position_with_margins(self, active_id):
        """Update gradient position with compensation for margins"""
        if self.frame and active_id:
            # If the active button is realized, we want to force a position recalculation
            # This ensures we have the correct positions with margins applied
            active_button = self.workspace_buttons.get(active_id)
            
            if active_button and active_button.get_realized():
                # Now that button and margins are realized, start the animation
                position = self.calculate_gradient_position(active_id)
                current_position = self.animation_current_position
                self.animate_gradient(current_position, position)
            else:
                # Button not realized yet, try again shortly
                GLib.timeout_add(20, self.update_gradient_position_with_margins, active_id)
                return False
        
        return False  # Don't repeat
    
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
