import tkinter as tk

window = tk.Tk()
window.title("Text Window")

# Set window size (e.g., 600x300)
window.geometry("600x300")

# Create a frame with padding (margin)
frame = tk.Frame(window, padx=50, pady=50)  # 50px padding on all sides
frame.pack(expand=True)

# Add a larger label inside the frame
label = tk.Label(frame, text="Hello, World!", font=("Arial", 24))  # Bigger font
label.pack()

window.mainloop()

