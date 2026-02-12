import pyautogui
import time
import tkinter as tk
from threading import Thread
import keyboard
from pynput.mouse import Controller

#  █████╗ ██╗   ██╗████████╗ ██████╗ 
# ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗
# ███████║██║   ██║   ██║   ██║   ██║
# ██╔══██║██║   ██║   ██║   ██║   ██║
# ██║  ██║╚██████╔╝   ██║   ╚██████╔╝
# ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝

class AutomationUI:
    def __init__(self):
        self.running = False
        self.keybinds_enabled = False
        self.mouse = Controller()
        self.loop_count = 0
        self.set_count = 0
        
        self.window = tk.Tk()
        self.window.title("Auto")
        self.window.geometry("250x100")
        self.window.resizable(False, False)

        self.window.attributes('-topmost', 1)
        self.window.lift()

        # Status
        self.status_label = tk.Label(self.window, text="Status: Stopped", font=("Arial", 10, "bold"), fg="red")
        self.status_label.pack()

        # Counter
        self.counter_label = tk.Label(
            self.window,
            text="Set: 0 / 3 | Loops: 0 / 9",
            font=("Arial", 10, "bold"),
            fg="blue"
        )
        self.counter_label.pack()

        # Control Frame (Input + Run + Key in one row)
        self.control_frame = tk.Frame(self.window)
        self.control_frame.pack(pady=5, expand=True)

        self.input_entry = tk.Entry(self.control_frame, width=5, justify="center",
                                    font=("Arial", 12, "bold"))
        self.input_entry.insert(0, "200k")
        self.input_entry.grid(row=0, column=0, padx=1)

        # Toggle Start/Stop Button
        self.toggle_btn = tk.Button(
            self.control_frame,
            text="Run",
            command=self.toggle_running,
            bg="green",
            fg="white",
            width=7,
            font=("Arial", 10, "bold")
        )
        self.toggle_btn.grid(row=0, column=1, padx=1)

        # Enable Keybind Button
        self.toggle_keybind_btn = tk.Button(
            self.control_frame,
            text="Key",
            command=self.toggle_keybinds,
            bg="white",
            fg="red",
            width=7,
            font=("Arial", 10, "bold")
        )
        self.toggle_keybind_btn.grid(row=0, column=2, padx=1)

        keyboard.add_hotkey('o', self.hotkey_start)
        keyboard.add_hotkey('p', self.hotkey_stop)

        self.window.mainloop()

    def update_counter(self):
        self.counter_label.config(
            text=f"Set: {self.set_count} / 3 | Loops: {self.loop_count} / 9"
        )

    def copy_text(self):
        value = self.input_entry.get()
        text = f"/ah sell {value}"
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        self.window.update()

    def toggle_keybinds(self):
        self.keybinds_enabled = not self.keybinds_enabled

        if self.keybinds_enabled:
            # Enabled → Green text
            self.toggle_keybind_btn.config(fg="green")
        else:
            # Disabled → Red text
            self.toggle_keybind_btn.config(fg="red")

    def hotkey_start(self):
        if self.keybinds_enabled:
            self.start()

    def hotkey_stop(self):
        if self.keybinds_enabled:
            self.stop()

    # TOGGLE FUNCTION
    def toggle_running(self):
        if not self.running:
            self.start()
            self.toggle_btn.config(text="Stop (P)", bg="red")
        else:
            self.stop()
            self.toggle_btn.config(text="Run", bg="green")

    def start(self):
        if not self.running:
            self.running = True
            self.loop_count = 0
            self.set_count = 0
            self.update_counter()

            self.status_label.config(text="Status: Selling", fg="green")
            self.toggle_btn.config(text="Stop (P)", bg="red")

            thread = Thread(target=self.run_automation)
            thread.daemon = True
            thread.start()

    def stop(self):
        if self.running:
            self.running = False
            self.status_label.config(text="Status: Stopped", fg="red")
            self.toggle_btn.config(text="Run", bg="green")

    def drag_sequence(self, y_coord):
        try:
            pyautogui.press('e')
            time.sleep(0.3)

            pyautogui.keyDown('shift')
            time.sleep(0.2)

            pyautogui.moveTo(1245, y_coord, duration=0.2)
            time.sleep(0.1)

            pyautogui.mouseDown(button='left')
            time.sleep(0.1)

            pyautogui.moveTo(670, y_coord, duration=0.5)
            time.sleep(0.1)

            pyautogui.mouseUp(button='left')
            time.sleep(0.1)

            pyautogui.keyUp('shift')
            time.sleep(0.3)

            pyautogui.press('esc')
            time.sleep(0.2)

        except:
            try:
                pyautogui.keyUp('shift')
            except:
                pass

    def run_automation(self):
        self.copy_text()

        y_coordinates = [700, 650, 550]
        self.set_count = 0
        self.update_counter()

        while self.running and self.set_count < 3:
            y_coord = y_coordinates[self.set_count]

            self.status_label.config(text=f"Status: Drag (y={y_coord})", fg="orange")
            self.drag_sequence(y_coord)

            if not self.running:
                break

            self.status_label.config(text="Status: Waiting...", fg="blue")
            time.sleep(1.0)

            if not self.running:
                break

            self.loop_count = 0
            self.status_label.config(text="Status: Selling", fg="green")
            self.update_counter()

            while self.running and self.loop_count < 9:
                pyautogui.press('t')
                pyautogui.hotkey('ctrl', 'v')
                pyautogui.press('enter')
                pyautogui.click(1101, 364, duration=0.3)
                self.mouse.scroll(0, 1)

                self.loop_count += 1
                self.update_counter()

            self.set_count += 1
            self.update_counter()

        self.stop()

if __name__ == "__main__":
    AutomationUI()
