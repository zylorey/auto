import pyautogui
import time
import tkinter as tk
from threading import Thread
import keyboard
from pynput.mouse import Controller, Button

class AutomationUI:
    def __init__(self):
        self.running = False
        self.keybinds_enabled = True
        self.mouse = Controller()
        self.loop_count = 0
        self.window = tk.Tk()
        self.window.title("Auto")
        self.window.geometry("250x250")
        self.window.resizable(False, False)
        
        # Always on top
        self.window.attributes('-topmost', 1)
        self.window.lift()
        
        # Status
        self.status_label = tk.Label(self.window, text="Status: Stopped", font=("Arial", 10), fg="red")
        self.status_label.pack(pady=0)
        
        # Loop counter
        self.counter_label = tk.Label(self.window, text="Loops: 0 / 9", font=("Arial", 10), fg="blue")
        self.counter_label.pack(pady=0)
        
        # Keybind status
        self.keybind_label = tk.Label(self.window, text="Keybinds: Enabled", font=("Arial", 10), fg="green")
        self.keybind_label.pack(pady=0)
        
        # Shortcut info
        tk.Label(self.window, text="Press 'O' to Start | 'P' to Stop", font=("Arial", 10), fg="blue").pack(pady=0)
        
        # Copy Command button (new feature)
        self.copy_btn = tk.Button(self.window, text="Copy Command", command=self.copy_text, bg="purple", fg="white", width=18)
        self.copy_btn.pack(pady=0)
        
        # Buttons (wider)
        self.start_btn = tk.Button(self.window, text="Start (O)", command=self.start, bg="green", fg="white", width=18)
        self.start_btn.pack(pady=0)
        
        self.stop_btn = tk.Button(self.window, text="Stop (P)", command=self.stop, bg="red", fg="white", width=18, state="disabled")
        self.stop_btn.pack(pady=0)
        
        # Toggle keybind button
        self.toggle_keybind_btn = tk.Button(self.window, text="Disable Keybinds", command=self.toggle_keybinds, bg="orange", fg="white", width=18)
        self.toggle_keybind_btn.pack(pady=0)
        
        # Setup global hotkeys
        keyboard.add_hotkey('o', self.hotkey_start)
        keyboard.add_hotkey('p', self.hotkey_stop)
        
        self.window.mainloop()
    
    def copy_text(self):
        """Copy the command to clipboard"""
        text = "/ah sell 200k"
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        self.window.update()
    
    def toggle_keybinds(self):
        self.keybinds_enabled = not self.keybinds_enabled
        if self.keybinds_enabled:
            self.keybind_label.config(text="Keybinds: Enabled", fg="green")
            self.toggle_keybind_btn.config(text="Disable Keybinds")
        else:
            self.keybind_label.config(text="Keybinds: Disabled", fg="red")
            self.toggle_keybind_btn.config(text="Enable Keybinds")
    
    def hotkey_start(self):
        if self.keybinds_enabled:
            self.start()
    
    def hotkey_stop(self):
        if self.keybinds_enabled:
            self.stop()
    
    def start(self):
        if not self.running:
            self.running = True
            self.loop_count = 0
            self.status_label.config(text="Status: Running", fg="green")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            
            # Run automation in separate thread
            thread = Thread(target=self.run_automation)
            thread.daemon = True
            thread.start()
    
    def stop(self):
        if self.running:
            self.running = False
            self.status_label.config(text="Status: Stopped", fg="red")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
    
    def run_automation(self):
        while self.running and self.loop_count < 9:
            self.counter_label.config(text=f"Loops: {self.loop_count} / 9")
            
            pyautogui.press('t')
            
            pyautogui.hotkey('ctrl', 'v')
            
            pyautogui.press('enter')
            
            # Instant click with no movement delay
            pyautogui.click(1101, 364, duration=0.3)
            
            # Scroll
            self.mouse.scroll(0, 1)
            
            self.loop_count += 1
        
        # Auto-stop after 9 loops
        if self.loop_count >= 9:
            self.counter_label.config(text="Loops: 9 / 9 - Complete!", fg="green")
            self.stop()

if __name__ == "__main__":
    AutomationUI()
    
