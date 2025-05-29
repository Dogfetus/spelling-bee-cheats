import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import sys
import io
import queue
from contextlib import redirect_stdout, redirect_stderr

# Import your AudioPassthrough class
# Assuming audio.py is in the same directory
try:
    from audio.audio import AudioPassthrough
except ImportError:
    messagebox.showerror("Import Error", "Could not import AudioPassthrough from audio.py")
    sys.exit(1)

class AudioRoutingWorker:
    """Separate worker class to handle audio routing in its own thread"""
    def __init__(self, message_queue):
        self.message_queue = message_queue
        self.passthrough = None
        self.is_running = False
        self.worker_thread = None
        self.stop_event = threading.Event()
        
    def start_routing(self, input_device_name, output_device_name, input_device_type, volume_multiplier):
        """Start audio routing in a separate thread"""
        if self.is_running:
            self.message_queue.put(("error", "Audio routing is already running"))
            return
            
        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._routing_worker, 
                                             args=(input_device_name, output_device_name, 
                                                  input_device_type, volume_multiplier),
                                             daemon=False)  # Not daemon so it continues even if GUI has issues
        self.worker_thread.start()
        
    def _routing_worker(self, input_device_name, output_device_name, input_device_type, volume_multiplier):
        """Main worker thread for audio routing"""
        try:
            self.is_running = True
            self.message_queue.put(("status", "Initializing audio routing..."))
            
            # Create passthrough instance
            self.passthrough = AudioPassthrough()
            
            # Capture any output from the start_passthrough method
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                success = self.passthrough.start_passthrough(
                    input_device_name=input_device_name,
                    output_device_name=output_device_name,
                    input_device_type=input_device_type,
                    volume_multiplier=volume_multiplier
                )
            
            # Get any output messages
            stdout_content = output_buffer.getvalue()
            stderr_content = error_buffer.getvalue()
            
            if success:
                self.message_queue.put(("success", "Audio routing started successfully"))
                if stdout_content.strip():
                    for line in stdout_content.strip().split('\n'):
                        if line.strip():
                            self.message_queue.put(("log", line.strip()))
                
                # Keep the routing alive until stop is requested
                self.message_queue.put(("status", "🎵 Audio routing active"))
                
                # Wait for stop signal or check periodically
                while not self.stop_event.wait(0.1):  # Check every 100ms
                    if not self.is_running:
                        break
                        
            else:
                error_msg = "Failed to start audio routing"
                if stderr_content.strip():
                    error_msg += f": {stderr_content.strip()}"
                self.message_queue.put(("error", error_msg))
                
        except Exception as e:
            self.message_queue.put(("error", f"Audio routing error: {str(e)}"))
        finally:
            # Always cleanup
            self._cleanup()
            
    def stop_routing(self):
        """Stop audio routing"""
        if not self.is_running:
            self.message_queue.put(("log", "No audio routing is currently active"))
            return
            
        try:
            self.message_queue.put(("status", "Stopping audio routing..."))
            
            # Signal the worker to stop
            self.stop_event.set()
            self.is_running = False
            
            # Stop the passthrough
            if self.passthrough:
                try:
                    self.passthrough.stop_passthrough()
                except Exception as e:
                    self.message_queue.put(("log", f"Warning during stop: {str(e)}"))
                    
            # Wait for worker thread to finish (with timeout)
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2.0)
                if self.worker_thread.is_alive():
                    self.message_queue.put(("log", "Warning: Worker thread did not stop cleanly"))
                    
            self.message_queue.put(("stopped", "Audio routing stopped successfully"))
            
        except Exception as e:
            self.message_queue.put(("error", f"Error stopping routing: {str(e)}"))
            # Force cleanup anyway
            self._cleanup()
            
    def _cleanup(self):
        """Clean up resources"""
        self.is_running = False
        if self.passthrough:
            try:
                self.passthrough.stop_passthrough()
            except:
                pass
            self.passthrough = None
        self.worker_thread = None

class AudioGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Passthrough Control")
        self.root.geometry("850x750")
        self.root.resizable(True, True)
        
        # Create message queue for communication with worker
        self.message_queue = queue.Queue()
        
        # Create audio worker
        self.audio_worker = AudioRoutingWorker(self.message_queue)
        
        # Dark theme colors
        self.colors = {
            'bg_primary': '#1e1e1e',      # Main background
            'bg_secondary': '#2d2d2d',    # Secondary background
            'bg_tertiary': '#3d3d3d',     # Elevated elements
            'accent': '#007acc',          # Accent blue
            'accent_hover': '#1e90ff',    # Hover state
            'success': '#28a745',         # Success green
            'danger': '#dc3545',          # Danger red
            'text_primary': '#ffffff',    # Primary text
            'text_secondary': '#b3b3b3',  # Secondary text
            'border': '#404040',          # Border color
        }
        
        # Configure root window
        self.root.configure(bg=self.colors['bg_primary'])
        
        # Initialize state
        self.is_routing = False
        
        # Setup modern styling
        self.setup_styles()
        
        # Create main interface
        self.create_widgets()
        
        # Start message processing
        self.process_messages()
        
        # Load devices on startup
        self.refresh_devices()
        
    def setup_styles(self):
        """Configure modern dark theme styles"""
        style = ttk.Style()
        
        # Configure overall theme
        style.theme_use('clam')
        
        # Main frame styling
        style.configure('Dark.TFrame', 
                       background=self.colors['bg_primary'],
                       borderwidth=0)
        
        # Label styling
        style.configure('Dark.TLabel',
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 10))
        
        style.configure('Title.TLabel',
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 18, 'bold'))
        
        style.configure('Status.TLabel',
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['accent'],
                       font=('Segoe UI', 11, 'bold'),
                       padding=(10, 5))
        
        # LabelFrame styling
        style.configure('Dark.TLabelframe',
                       background=self.colors['bg_primary'],
                       bordercolor=self.colors['border'],
                       darkcolor=self.colors['bg_secondary'],
                       lightcolor=self.colors['bg_secondary'],
                       borderwidth=1,
                       relief='solid')
        
        style.configure('Dark.TLabelframe.Label',
                       background=self.colors['bg_primary'],
                       foreground=self.colors['accent'],
                       font=('Segoe UI', 11, 'bold'))
        
        # Button styling
        style.configure('Modern.TButton',
                       background=self.colors['bg_tertiary'],
                       foreground=self.colors['text_primary'],
                       bordercolor=self.colors['border'],
                       focuscolor='none',
                       darkcolor=self.colors['bg_tertiary'],
                       lightcolor=self.colors['bg_tertiary'],
                       borderwidth=1,
                       relief='solid',
                       padding=(15, 8),
                       font=('Segoe UI', 10))
        
        style.map('Modern.TButton',
                 background=[('active', self.colors['bg_secondary']),
                           ('pressed', self.colors['border'])])
        
        # Accent button styling
        style.configure('Accent.TButton',
                       background=self.colors['accent'],
                       foreground='white',
                       bordercolor=self.colors['accent'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat',
                       padding=(20, 10),
                       font=('Segoe UI', 11, 'bold'))
        
        style.map('Accent.TButton',
                 background=[('active', self.colors['accent_hover']),
                           ('pressed', '#005a9e')])
        
        # Success button styling
        style.configure('Success.TButton',
                       background=self.colors['success'],
                       foreground='white',
                       bordercolor=self.colors['success'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat',
                       padding=(20, 10),
                       font=('Segoe UI', 11, 'bold'))
        
        style.map('Success.TButton',
                 background=[('active', '#218838'),
                           ('pressed', '#1e7e34')])
        
        # Danger button styling  
        style.configure('Danger.TButton',
                       background=self.colors['danger'],
                       foreground='white',
                       bordercolor=self.colors['danger'],
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat',
                       padding=(20, 10),
                       font=('Segoe UI', 11, 'bold'))
        
        style.map('Danger.TButton',
                 background=[('active', '#c82333'),
                           ('pressed', '#bd2130')])
        
        # Combobox styling
        style.configure('Dark.TCombobox',
                       fieldbackground=self.colors['bg_tertiary'],
                       background=self.colors['bg_tertiary'],
                       foreground=self.colors['text_primary'],
                       bordercolor=self.colors['border'],
                       arrowcolor=self.colors['text_secondary'],
                       insertcolor=self.colors['text_primary'],
                       selectbackground=self.colors['accent'],
                       selectforeground='white',
                       font=('Segoe UI', 10))
        
        # Scale styling
        style.configure('Dark.Horizontal.TScale',
                       background=self.colors['bg_primary'],
                       troughcolor=self.colors['bg_tertiary'],
                       bordercolor=self.colors['border'],
                       lightcolor=self.colors['accent'],
                       darkcolor=self.colors['accent'],
                       focuscolor='none')
        
        # Radiobutton styling
        style.configure('Dark.TRadiobutton',
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       focuscolor='none',
                       font=('Segoe UI', 10))
        
        style.map('Dark.TRadiobutton',
                 background=[('active', self.colors['bg_primary'])],
                 foreground=[('active', self.colors['text_primary'])])
        
    def create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="20", style='Dark.TFrame')
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title with modern styling
        title_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        title_frame.grid(row=0, column=0, columnspan=3, pady=(0, 30))
        
        title_label = ttk.Label(title_frame, text="🎵 Audio Passthrough Control", 
                               style='Title.TLabel')
        title_label.pack()
        
        subtitle_label = ttk.Label(title_frame, text="Route audio between devices with precision", 
                                  style='Dark.TLabel',
                                  font=('Segoe UI', 10))
        subtitle_label.pack(pady=(5, 0))
        
        # Device refresh button
        refresh_btn = ttk.Button(main_frame, text="🔄 Refresh Devices", 
                                command=self.refresh_devices, style='Modern.TButton')
        refresh_btn.grid(row=1, column=0, columnspan=3, pady=(0, 20), sticky=tk.W)
        
        # Input source section
        input_frame = ttk.LabelFrame(main_frame, text="📥 Input Source", 
                                    padding="20", style='Dark.TLabelframe')
        input_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        input_frame.columnconfigure(1, weight=1)
        
        # Input type selection
        ttk.Label(input_frame, text="Source Type:", style='Dark.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 15))
        
        self.input_type = tk.StringVar(value="loopback")
        input_type_frame = ttk.Frame(input_frame, style='Dark.TFrame')
        input_type_frame.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Radiobutton(input_type_frame, text="Loopback (System Audio)", 
                       variable=self.input_type, value="loopback",
                       command=self.on_input_type_change, 
                       style='Dark.TRadiobutton').pack(side=tk.LEFT, padx=(0, 30))
        ttk.Radiobutton(input_type_frame, text="Microphone", 
                       variable=self.input_type, value="microphone",
                       command=self.on_input_type_change,
                       style='Dark.TRadiobutton').pack(side=tk.LEFT)
        
        # Input device selection
        ttk.Label(input_frame, text="Device:", style='Dark.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=(0, 15), pady=(15, 0))
        
        self.input_device_var = tk.StringVar()
        self.input_device_combo = ttk.Combobox(input_frame, textvariable=self.input_device_var, 
                                              state="readonly", width=55, style='Dark.TCombobox')
        self.input_device_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(15, 0))
        
        # Output section
        output_frame = ttk.LabelFrame(main_frame, text="📤 Output Destination", 
                                     padding="20", style='Dark.TLabelframe')
        output_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        output_frame.columnconfigure(1, weight=1)
        
        ttk.Label(output_frame, text="Device:", style='Dark.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 15))
        
        self.output_device_var = tk.StringVar()
        self.output_device_combo = ttk.Combobox(output_frame, textvariable=self.output_device_var, 
                                               state="readonly", width=55, style='Dark.TCombobox')
        self.output_device_combo.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # Volume control section
        volume_frame = ttk.LabelFrame(main_frame, text="🔊 Volume Control", 
                                     padding="20", style='Dark.TLabelframe')
        volume_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        volume_frame.columnconfigure(1, weight=1)
        
        ttk.Label(volume_frame, text="Volume:", style='Dark.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 15))
        
        self.volume_var = tk.DoubleVar(value=1.0)
        volume_scale = ttk.Scale(volume_frame, from_=0.1, to=2.0, variable=self.volume_var, 
                                orient=tk.HORIZONTAL, length=400, style='Dark.Horizontal.TScale')
        volume_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15))
        
        self.volume_label = ttk.Label(volume_frame, text="1.0x", style='Dark.TLabel',
                                     font=('Segoe UI', 10, 'bold'))
        self.volume_label.grid(row=0, column=2)
        
        # Update volume label when scale changes
        volume_scale.configure(command=self.update_volume_label)
        
        # Control buttons with modern styling
        button_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        button_frame.grid(row=5, column=0, columnspan=3, pady=30)
        
        self.start_btn = ttk.Button(button_frame, text="▶️ Start Routing", 
                                   command=self.start_routing, style="Success.TButton")
        self.start_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        self.stop_btn = ttk.Button(button_frame, text="⏹️ Stop Routing", 
                                  command=self.stop_routing, state="disabled", style="Danger.TButton")
        self.stop_btn.pack(side=tk.LEFT)
        
        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="📊 Status & Log", 
                                     padding="20", style='Dark.TLabelframe')
        status_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # Status display with background
        status_container = ttk.Frame(status_frame, style='Dark.TFrame')
        status_container.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        status_container.configure(relief='solid', borderwidth=1)
        
        self.status_var = tk.StringVar(value="Ready to route audio")
        status_label = ttk.Label(status_container, textvariable=self.status_var, 
                                style='Status.TLabel')
        status_label.pack(fill=tk.X)
        
        # Log text area with dark styling
        self.log_text = scrolledtext.ScrolledText(
            status_frame, height=10, width=80,
            bg=self.colors['bg_tertiary'], 
            fg=self.colors['text_primary'], 
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['accent'],
            selectforeground='white',
            font=('Consolas', 9),
            relief='solid',
            borderwidth=1,
            highlightthickness=0
        )
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Clear log button
        clear_log_btn = ttk.Button(status_frame, text="🗑️ Clear Log", 
                                  command=self.clear_log, style='Modern.TButton')
        clear_log_btn.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
    
    def process_messages(self):
        """Process messages from the audio worker thread"""
        try:
            while True:
                try:
                    message_type, message = self.message_queue.get_nowait()
                    
                    if message_type == "log":
                        self.log_message(message)
                    elif message_type == "status":
                        self.status_var.set(message)
                        self.log_message(message)
                    elif message_type == "success":
                        self.is_routing = True
                        self.start_btn.config(state="disabled")
                        self.stop_btn.config(state="normal")
                        self.log_message(message)
                    elif message_type == "error":
                        self.is_routing = False
                        self.start_btn.config(state="normal")
                        self.stop_btn.config(state="disabled")
                        self.status_var.set("Error occurred")
                        self.log_message(f"ERROR: {message}")
                    elif message_type == "stopped":
                        self.is_routing = False
                        self.start_btn.config(state="normal")
                        self.stop_btn.config(state="disabled")
                        self.status_var.set("Ready to route audio")
                        self.log_message(message)
                        
                except queue.Empty:
                    break
                    
        except Exception as e:
            self.log_message(f"Error processing messages: {str(e)}")
        
        # Schedule next message processing
        self.root.after(100, self.process_messages)  # Check every 100ms
        
    def log_message(self, message):
        """Add message to log with timestamp"""
        try:
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.root.update_idletasks()
        except Exception as e:
            print(f"Error logging message: {e}")
    
    def clear_log(self):
        """Clear the log text area"""
        try:
            self.log_text.delete(1.0, tk.END)
        except Exception as e:
            print(f"Error clearing log: {e}")
    
    def update_volume_label(self, value):
        """Update the volume label when scale changes"""
        try:
            volume = float(value)
            self.volume_label.config(text=f"{volume:.1f}x")
        except Exception as e:
            print(f"Error updating volume label: {e}")
    
    def on_input_type_change(self):
        """Handle input type radio button changes"""
        try:
            self.populate_input_devices()
        except Exception as e:
            self.log_message(f"Error changing input type: {str(e)}")
    
    def refresh_devices(self):
        """Refresh and populate device lists"""
        try:
            self.log_message("Refreshing audio devices...")
            
            # Create temporary AudioPassthrough to get devices
            temp_passthrough = AudioPassthrough()
            
            # Capture device listing output
            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                self.output_devices, self.input_devices, self.loopback_devices = temp_passthrough.list_devices()
            
            # Log the device discovery
            device_output = output_buffer.getvalue()
            if device_output:
                self.log_message("Device discovery completed")
            
            # Populate comboboxes
            self.populate_input_devices()
            self.populate_output_devices()
            
            self.log_message(f"Found {len(self.output_devices)} output devices, "
                           f"{len(self.input_devices)} input devices, "
                           f"{len(self.loopback_devices)} loopback devices")
            
        except Exception as e:
            error_msg = f"Error refreshing devices: {str(e)}"
            self.log_message(error_msg)
            print(f"Device refresh error: {e}")  # Also print to console
    
    def populate_input_devices(self):
        """Populate input device combobox based on selected type"""
        try:
            self.input_device_combo['values'] = []
            
            if self.input_type.get() == "loopback":
                if hasattr(self, 'loopback_devices'):
                    device_names = [f"{device['name']}" for device in self.loopback_devices]
                    self.input_device_combo['values'] = device_names
                    if device_names:
                        self.input_device_combo.set(device_names[0])
            else:  # microphone
                if hasattr(self, 'input_devices'):
                    device_names = [f"{device['name']}" for device in self.input_devices]
                    self.input_device_combo['values'] = device_names
                    if device_names:
                        self.input_device_combo.set(device_names[0])
        except Exception as e:
            self.log_message(f"Error populating input devices: {str(e)}")
    
    def populate_output_devices(self):
        """Populate output device combobox"""
        try:
            if hasattr(self, 'output_devices'):
                device_names = [f"{device['name']}" for device in self.output_devices]
                self.output_device_combo['values'] = device_names
                if device_names:
                    self.output_device_combo.set(device_names[0])
        except Exception as e:
            self.log_message(f"Error populating output devices: {str(e)}")
    
    def find_device_by_name(self, name, device_list):
        """Find device object by name from device list"""
        for device in device_list:
            if device['name'] == name:
                return device
        return None
    
    def start_routing(self):
        """Start audio routing using the worker thread"""
        try:
            if self.is_routing:
                self.log_message("Audio routing is already active!")
                return
                
            # Get selected devices
            input_name = self.input_device_var.get()
            output_name = self.output_device_var.get()
            
            if not input_name or not output_name:
                messagebox.showwarning("Selection Error", "Please select both input and output devices")
                return
            
            # Find device objects
            if self.input_type.get() == "loopback":
                input_device = self.find_device_by_name(input_name, self.loopback_devices)
                input_device_type = "loopback"
            else:
                input_device = self.find_device_by_name(input_name, self.input_devices)
                input_device_type = "input"
            
            output_device = self.find_device_by_name(output_name, self.output_devices)
            
            if not input_device or not output_device:
                messagebox.showerror("Device Error", "Could not find selected devices")
                return
            
            # Get volume setting
            volume = self.volume_var.get()
            
            # Log configuration
            self.log_message(f"Starting audio routing:")
            self.log_message(f"  Input: {input_device['name']} ({input_device_type})")
            self.log_message(f"  Output: {output_device['name']}")
            self.log_message(f"  Volume: {volume:.1f}x")
            
            # Start routing using worker
            self.audio_worker.start_routing(input_name, output_name, input_device_type, volume)
            
        except Exception as e:
            error_msg = f"Error starting routing: {str(e)}"
            self.log_message(error_msg)
            print(f"Start routing error: {e}")  # Also print to console
    
    def stop_routing(self):
        """Stop audio routing using the worker thread"""
        try:
            if not self.is_routing:
                self.log_message("No audio routing is currently active")
                return
                
            self.log_message("Requesting stop...")
            
            # Request stop from worker
            self.audio_worker.stop_routing()
            
        except Exception as e:
            error_msg = f"Error stopping routing: {str(e)}"
            self.log_message(error_msg)
            print(f"Stop routing error: {e}")  # Also print to console
    
    def on_closing(self):
        """Handle window closing"""
        try:
            if self.is_routing:
                if messagebox.askokcancel("Quit", "Audio routing is active. Stop routing and quit?"):
                    # Stop the audio worker
                    self.audio_worker.stop_routing()
                    # Give it a moment to stop
                    time.sleep(0.5)
                    self.root.destroy()
            else:
                self.root.destroy()
        except Exception as e:
            print(f"Error during closing: {e}")
            self.root.destroy()  # Force close if there's an error

def run():
    """Main function to run the GUI"""
    try:
        root = tk.Tk()
        
        # Create the GUI
        app = AudioGUI(root)
        
        # Handle window closing
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # Center the window
        root.update_idletasks()
        x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
        y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
        root.geometry(f"+{x}+{y}")
        
        # Start the GUI
        root.mainloop()
        
    except Exception as e:
        print(f"Critical error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()