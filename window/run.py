import tkinter as tk
from tkinter import scrolledtext
import queue

def run_gui(text_queue):
    """Run the GUI window with speech recognition display"""

    def update_text_display():
        """Update the text display with recognized speech"""
        try:
            while True:
                text = text_queue.get_nowait()
                text_display.insert(tk.END, f"{text}\n")
                text_display.see(tk.END)  # Scroll to bottom
        except queue.Empty:
            pass

        # Schedule next update
        window.after(100, update_text_display)
    
    def clear_text():
        """Clear the text display"""
        text_display.delete(1.0, tk.END)
    
    # Create main window
    window = tk.Tk()
    window.title("Virtual Speaker - Speech Recognition")
    window.geometry("800x600")
    
    # Create main frame
    main_frame = tk.Frame(window, padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title label
    title_label = tk.Label(main_frame, text="Speech Recognition Output", 
                          font=("Arial", 18, "bold"))
    title_label.pack(pady=(0, 10))
    
    # Status label
    status_label = tk.Label(main_frame, text="🎤 Listening for speech...", 
                           font=("Arial", 12), fg="green")
    status_label.pack(pady=(0, 10))
    
    # Text display area
    text_display = scrolledtext.ScrolledText(
        main_frame, 
        wrap=tk.WORD, 
        font=("Arial", 14),
        height=20,
        width=70
    )
    text_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    # Control buttons
    button_frame = tk.Frame(main_frame)
    button_frame.pack(fill=tk.X)
    
    clear_button = tk.Button(button_frame, text="Clear Text", 
                            command=clear_text, font=("Arial", 12))
    clear_button.pack(side=tk.RIGHT)
    
    # Start updating the display
    update_text_display()
    
    # Run the GUI
    window.mainloop()
