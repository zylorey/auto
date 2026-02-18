import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageGrab
import pyautogui
import pyperclip
import threading
import time
import keyboard
from pynput import mouse
from mss import mss
import pywinstyles
import sv_ttk

def apply_theme_to_titlebar(root):
    root.after(1, lambda: pywinstyles.change_header_color(root, "#1c1c1c"))

class HotbarDetector:
    """Hotbar detector for checking if selected slot has block or is empty"""
    def __init__(self):
        # Hotbar region coordinates (720x87 pixels)
        self.hotbar_region = {
            'left': 600,
            'top': 933,
            'width': 1320 - 600,  # 720 pixels wide
            'height': 1020 - 933   # 87 pixels tall
        }
        
        # Hotbar has 9 slots
        self.num_slots = 9
        self.slot_width = self.hotbar_region['width'] / self.num_slots
    
    def capture_hotbar(self):
        """Capture the hotbar region from the screen"""
        try:
            with mss() as sct:
                screenshot = sct.grab(self.hotbar_region)
                img = np.array(screenshot)
                # Convert BGRA to BGR
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img
        except Exception as e:
            print(f"Error capturing hotbar: {e}")
            return None
    
    def find_selected_slot(self, img):
        """
        Find which slot is currently selected
        Returns the slot index (0-8) or -1 if not found
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Look for bright pixels that indicate selection border
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Check each slot for selection indicator
        max_brightness = 0
        selected_slot = -1
        
        for slot_idx in range(self.num_slots):
            slot_x_start = int(slot_idx * self.slot_width)
            slot_x_end = int((slot_idx + 1) * self.slot_width)
            
            # Check all edges (top, bottom, left, right) for bright border
            top_edge = thresh[0:8, slot_x_start:slot_x_end]
            bottom_edge = thresh[-8:, slot_x_start:slot_x_end]
            
            # Also check for vertical borders within the slot
            if slot_x_start < thresh.shape[1] and slot_x_end <= thresh.shape[1]:
                left_edge = thresh[:, slot_x_start:min(slot_x_start+5, slot_x_end)]
                right_edge = thresh[:, max(slot_x_start, slot_x_end-5):slot_x_end]
                
                # Sum all edge brightness
                total_brightness = (np.sum(top_edge) + np.sum(bottom_edge) + 
                                  np.sum(left_edge) + np.sum(right_edge))
                
                # Track the slot with maximum brightness (selected slot has bright border)
                if total_brightness > max_brightness and total_brightness > 2000:
                    max_brightness = total_brightness
                    selected_slot = slot_idx
        
        return selected_slot
    
    def analyze_slot(self, img, slot_idx):
        """
        Analyze a specific slot for block content
        Returns (has_block, variance)
        """
        if slot_idx < 0 or slot_idx >= self.num_slots:
            return (False, 0)
        
        # Extract the slot region
        slot_x_start = int(slot_idx * self.slot_width)
        slot_x_end = int((slot_idx + 1) * self.slot_width)
        
        # Get center region
        full_slot = img[:, slot_x_start:slot_x_end]
        h, w = full_slot.shape[:2]
        center_y_start = int(h * 0.25)
        center_y_end = int(h * 0.75)
        center_x_start = int(w * 0.25)
        center_x_end = int(w * 0.75)
        
        center_region = full_slot[center_y_start:center_y_end, center_x_start:center_x_end]
        
        if center_region.size == 0:
            return (False, 0)
        
        # Convert to grayscale
        gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
        
        # Calculate variance
        variance = np.var(gray)
        
        # Simple detection: variance > 1000 = BLOCK, otherwise NOTHING
        has_block = variance > 1000
        
        return (has_block, variance)
    
    def check_current_slot(self):
        """Check if current selected hotbar slot has a block"""
        img = self.capture_hotbar()
        if img is None:
            return False, 0
        
        slot_idx = self.find_selected_slot(img)
        has_block, variance = self.analyze_slot(img, slot_idx)
        
        return has_block, variance


class HotbarDetectorGUI:
    """GUI for live hotbar detection"""
    def __init__(self, root):
        self.window = tk.Toplevel(root)
        self.window.title("Hotbar Detector")
        self.window.geometry("470x112+1400+50")  # Width x Height + X position + Y position
        self.window.resizable(False, False)
        self.window.attributes('-topmost', 1)
        
        # Apply dark title bar
        apply_theme_to_titlebar(self.window)
        
        self.hotbar_detector = HotbarDetector()
        
        # Detection state
        self.running = False
        self.current_slot = -1
        self.has_block = False
        
        # Start detection thread
        self.detection_thread = None
        
        # Create GUI elements
        self.create_widgets()
        
        # Auto-start detection after a short delay
        self.window.after(100, self.start_detection)
    
    def create_widgets(self):
        """Create all GUI elements"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="2")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== TOP - INFO (HORIZONTAL LAYOUT) =====
        info_frame = ttk.Frame(main_frame, padding="1")
        info_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 0))
        
        # Slot display
        slot_frame = ttk.Frame(info_frame)
        slot_frame.grid(row=0, column=0, padx=5)
        
        ttk.Label(slot_frame, text="SLOT", 
                 font=("Arial", 7, "bold"), foreground="orange").pack()
        self.slot_label = ttk.Label(slot_frame, text="None", 
                                    font=("Arial", 16, "bold"), 
                                    foreground="orange")
        self.slot_label.pack()
        
        # Separator
        ttk.Separator(info_frame, orient=tk.VERTICAL).grid(row=0, column=1, sticky=(tk.N, tk.S), padx=3)
        
        # Status display (checkmark/cross)
        status_frame = ttk.Frame(info_frame)
        status_frame.grid(row=0, column=2, padx=5)
        
        ttk.Label(status_frame, text="STATUS", 
                 font=("Arial", 7, "bold"), foreground="gray").pack()
        self.status_label = ttk.Label(status_frame, text="N/A", 
                                     font=("Arial", 16, "bold"), 
                                     foreground="gray")
        self.status_label.pack()
        
        # Separator
        ttk.Separator(info_frame, orient=tk.VERTICAL).grid(row=0, column=3, sticky=(tk.N, tk.S), padx=3)
        
        # Variance display
        variance_frame = ttk.Frame(info_frame)
        variance_frame.grid(row=0, column=4, padx=5)
        
        ttk.Label(variance_frame, text="VARIANCE", 
                 font=("Arial", 7, "bold"), foreground="blue").pack()
        self.variance_label = ttk.Label(variance_frame, text="0", 
                                       font=("Arial", 16, "bold"), 
                                       foreground="blue")
        self.variance_label.pack()
        
        # ===== BOTTOM - LIVE VIEW =====
        # Live view canvas
        self.canvas = tk.Canvas(
            main_frame, 
            width=460, 
            height=55,
        )
        self.canvas.pack(side=tk.TOP, pady=0)
    
    def draw_detection_overlay(self, img, slot_idx, has_block):
        """Draw detection visualization on the image"""
        # Draw slot boundaries
        for i in range(self.hotbar_detector.num_slots + 1):
            x = int(i * self.hotbar_detector.slot_width)
            cv2.line(img, (x, 0), (x, img.shape[0]), (50, 50, 50), 1)
        
        # Draw slot numbers
        for i in range(self.hotbar_detector.num_slots):
            x = int(i * self.hotbar_detector.slot_width + self.hotbar_detector.slot_width / 2)
            cv2.putText(img, str(i + 1), (x - 8, 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        
        # Highlight selected slot
        if slot_idx != -1:
            slot_x_start = int(slot_idx * self.hotbar_detector.slot_width)
            slot_x_end = int((slot_idx + 1) * self.hotbar_detector.slot_width)
            
            # Draw colored border based on block status
            # Use larger inset (5 pixels) to prevent 3px thick border from being clipped
            color = (0, 255, 0) if has_block else (0, 0, 255)
            cv2.rectangle(img, (slot_x_start + 10, 10), 
                         (slot_x_end - 10, img.shape[0] - 10), 
                         color, 3)
        
        return img
    
    def update_display(self, img):
        """Update the canvas with the current image"""
        if img is None:
            return
        
        # Resize to fit canvas
        img_resized = cv2.resize(img, (460, 55))
        
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        img_pil = Image.fromarray(img_rgb)
        
        # Convert to PhotoImage
        img_tk = ImageTk.PhotoImage(image=img_pil)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(230, 27, image=img_tk)
        self.canvas.image = img_tk  # Keep a reference
    
    def update_status_labels(self, slot_idx, has_block, variance):
        """Update the status labels"""
        if slot_idx != -1:
            self.slot_label.config(text=f"{slot_idx + 1}/9", foreground="orange")
            
            if has_block:
                self.status_label.config(text="✓", foreground="green")
            else:
                self.status_label.config(text="✗", foreground="red")
        else:
            self.slot_label.config(text="None", foreground="orange")
            self.status_label.config(text="N/A", foreground="gray")
        
        self.variance_label.config(text=f"{int(variance)}", foreground="blue")
    
    def detection_loop(self):
        """Main detection loop running in separate thread"""
        while self.running:
            try:
                # Capture and process
                img = self.hotbar_detector.capture_hotbar()
                
                if img is not None:
                    slot_idx = self.hotbar_detector.find_selected_slot(img)
                    has_block, variance = self.hotbar_detector.analyze_slot(img, slot_idx)
                    
                    # Debug output - print values when slot changes
                    if slot_idx != self.current_slot or has_block != self.has_block:
                        print(f"\n--- Slot {slot_idx + 1 if slot_idx != -1 else 'None'} ---")
                        print(f"Block Status: {'BLOCK' if has_block else 'NOTHING'}")
                        print(f"Variance: {variance:.2f}")
                        self.current_slot = slot_idx
                        self.has_block = has_block
                    
                    # Draw overlay
                    img_display = self.draw_detection_overlay(
                        img.copy(), slot_idx, has_block
                    )
                    
                    # Update GUI (must be done in main thread)
                    self.window.after(0, self.update_display, img_display)
                    self.window.after(0, self.update_status_labels, 
                                  slot_idx, has_block, variance)
                
                time.sleep(0.05)  # 20 FPS
                
            except Exception as e:
                print(f"Error in hotbar detection loop: {e}")
                time.sleep(0.1)
    
    def start_detection(self):
        """Start the detection thread"""
        if not self.running:
            self.running = True
            self.detection_thread = threading.Thread(
                target=self.detection_loop, 
                daemon=True
            )
            self.detection_thread.start()
    
    def stop_detection(self):
        """Stop the detection thread"""
        self.running = False
        if self.detection_thread:
            self.detection_thread.join(timeout=1.0)
    
    def on_closing(self):
        """Handle window closing"""
        self.running = False
        if self.detection_thread:
            self.detection_thread.join(timeout=1.0)
        self.window.destroy()


class ChestDetectorGUI:
    """GUI for live chest detection"""
    def __init__(self, root):
        self.window = tk.Toplevel(root)
        self.window.title("Chest Monitor")
        self.window.geometry("330x163+1400+202")  # Width x Height + X position + Y position
        self.window.resizable(False, False)
        self.window.attributes('-topmost', True)
        
        # Apply dark title bar
        apply_theme_to_titlebar(self.window)
        
        # HARDCODED SETTINGS
        self.x1 = 635
        self.y1 = 255
        self.x2 = 1283
        self.y2 = 473
        self.threshold = 20
        self.refresh_rate = 500
        self.book_check_interval = 250
        self.paper_match_threshold = 0.6
        
        # Variables
        self.is_monitoring = False
        self.monitor_thread = None
        self.book_detection_thread = None
        self.book_template = None
        self.paper_template = None
        self.paper_template_gray = None
        
        # Debug counter
        self.debug_counter = 0
        
        # Results
        self.empty_slots = 0
        self.filled_slots = 0
        
        # Load templates
        self.load_book_template()
        self.load_paper_template()   # <-- NEW: load paper template on startup
        
        self.setup_ui()
        
        # Auto-start book detection
        self.start_book_detection()
    
    def load_book_template(self):
        """Load the book.png template for detection"""
        try:
            self.book_template = cv2.imread('book.png', cv2.IMREAD_UNCHANGED)
            if self.book_template is None:
                print("⚠️ WARNING: book.png not found")
            else:
                print(f"✅ Book template loaded! Size: {self.book_template.shape}")
        except Exception as e:
            print(f"❌ Error loading book.png: {e}")
            self.book_template = None

    def load_paper_template(self):
        """Load the paper.png template for empty slot detection"""
        try:
            self.paper_template = cv2.imread('paper.png', cv2.IMREAD_UNCHANGED)
            if self.paper_template is None:
                print("⚠️ WARNING: paper.png not found. Place paper.png in the same directory.")
                print("   Paper detection will fall back to intensity-based method.")
            else:
                print(f"✅ Paper template loaded! Size: {self.paper_template.shape}")

                # Convert BGRA -> BGR if alpha channel present
                if len(self.paper_template.shape) == 3 and self.paper_template.shape[2] == 4:
                    self.paper_template = cv2.cvtColor(self.paper_template, cv2.COLOR_BGRA2BGR)
                    print("   Converted from BGRA to BGR")

                # Pre-compute grayscale version for faster matching
                self.paper_template_gray = cv2.cvtColor(self.paper_template, cv2.COLOR_BGR2GRAY)
                print(f"   Grayscale template ready: {self.paper_template_gray.shape}")

        except Exception as e:
            print(f"❌ Error loading paper.png: {e}")
            self.paper_template = None
            self.paper_template_gray = None

    def detect_paper_in_slot(self, slot_roi, slot_index):
        """
        Detect if paper.png is present in a slot using multi-scale template matching.
        Returns (is_paper: bool, confidence: float)
        """
        if self.paper_template is None or self.paper_template_gray is None or slot_roi.size == 0:
            return False, 0.0

        try:
            template_h, template_w = self.paper_template.shape[:2]

            # Skip slots that are far too small relative to the template
            if slot_roi.shape[0] < template_h * 0.5 or slot_roi.shape[1] < template_w * 0.5:
                return False, 0.0

            slot_gray = cv2.cvtColor(slot_roi, cv2.COLOR_BGR2GRAY)

            # Try multiple scales to handle different slot sizes
            scales = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
            max_confidence = 0.0
            best_scale = 0.0

            for scale in scales:
                width  = int(self.paper_template_gray.shape[1] * scale)
                height = int(self.paper_template_gray.shape[0] * scale)

                # Skip if scaled template won't fit in the slot
                if width > slot_gray.shape[1] or height > slot_gray.shape[0]:
                    continue
                if width < 5 or height < 5:
                    continue

                scaled_template = cv2.resize(self.paper_template_gray, (width, height))

                result = cv2.matchTemplate(slot_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)

                if max_val > max_confidence:
                    max_confidence = max_val
                    best_scale = scale

            # Periodic debug output for first 3 slots
            self.debug_counter += 1
            if self.debug_counter % 30 == 0 and slot_index < 3:
                print(f"Slot {slot_index}: paper confidence={max_confidence:.3f}, best_scale={best_scale:.2f}, size={slot_roi.shape}")

            is_paper = max_confidence >= self.paper_match_threshold
            return is_paper, max_confidence

        except Exception as e:
            if self.debug_counter % 100 == 0:
                print(f"Paper detection error in slot {slot_index}: {e}")
            return False, 0.0

    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.window, padding="2")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # ===== TOP - INFO (HORIZONTAL LAYOUT) =====
        info_frame = ttk.Frame(main_frame, padding="1")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Empty slots
        empty_frame = ttk.Frame(info_frame)
        empty_frame.grid(row=0, column=0, padx=5)
        
        ttk.Label(empty_frame, text="EMPTY", 
                 font=("Arial", 7, "bold"), foreground="green").pack()
        self.empty_label = ttk.Label(empty_frame, text="0", 
                                    font=("Arial", 16, "bold"), 
                                    foreground="green")
        self.empty_label.pack()
        
        # Separator
        ttk.Separator(info_frame, orient=tk.VERTICAL).grid(row=0, column=1, sticky=(tk.N, tk.S), padx=3)
        
        # Filled slots
        filled_frame = ttk.Frame(info_frame)
        filled_frame.grid(row=0, column=2, padx=5)
        
        ttk.Label(filled_frame, text="FILLED", 
                 font=("Arial", 7, "bold"), foreground="red").pack()
        self.filled_label = ttk.Label(filled_frame, text="0", 
                                     font=("Arial", 16, "bold"), 
                                     foreground="red")
        self.filled_label.pack()
        
        # Separator
        ttk.Separator(info_frame, orient=tk.VERTICAL).grid(row=0, column=3, sticky=(tk.N, tk.S), padx=3)
        
        # Total slots
        total_frame = ttk.Frame(info_frame)
        total_frame.grid(row=0, column=4, padx=5)
        
        ttk.Label(total_frame, text="TOTAL", 
                 font=("Arial", 7, "bold"), foreground="blue").pack()
        self.total_label = ttk.Label(total_frame, text="0", 
                                    font=("Arial", 16, "bold"), 
                                    foreground="blue")
        self.total_label.pack()
        
        # Status indicator
        self.status_label = ttk.Label(info_frame, 
                                     text="●", 
                                     foreground="red", font=("Arial", 7))
        self.status_label.grid(row=0, column=5, padx=5)
        
        # ===== BOTTOM - VIDEO FEED =====
        video_frame = ttk.Frame(main_frame)
        video_frame.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # Calculate exact size for the captured region
        capture_width = self.x2 - self.x1
        capture_height = self.y2 - self.y1
        
        display_width = int(capture_width * 0.5)
        display_height = int(capture_height * 0.5)
        
        self.canvas = tk.Canvas(video_frame, bg="#292929", 
                               width=display_width, 
                               height=display_height,
                               highlightthickness=0)
        self.canvas.pack()
        
        # Add "Waiting for book..." text
        self.waiting_text = self.canvas.create_text(
            display_width // 2, 
            display_height // 2,
            text="Waiting for book...",
            font=("Arial", 10),
            fill="gray"
        )
    
    def detect_book_on_screen(self):
        """Detect if book.png is visible on screen"""
        if self.book_template is None:
            return False
        
        try:
            screenshot = ImageGrab.grab()
            screenshot_np = np.array(screenshot)
            screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            
            if len(self.book_template.shape) == 3 and self.book_template.shape[2] == 4:
                template_bgr = cv2.cvtColor(self.book_template, cv2.COLOR_BGRA2BGR)
            else:
                template_bgr = self.book_template
            
            result = cv2.matchTemplate(screenshot_cv, template_bgr, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            threshold = 0.8
            return max_val >= threshold
            
        except Exception as e:
            print(f"Book detection error: {e}")
            return False
    
    def book_detection_loop(self):
        """Background thread that checks for book presence"""
        while True:
            try:
                book_detected = self.detect_book_on_screen()
                
                if book_detected and not self.is_monitoring:
                    print("📖 Book detected! Starting monitoring...")
                    self.window.after(0, self.start_monitoring)
                    self.window.after(0, lambda: self.status_label.config(foreground="green"))
                elif not book_detected and self.is_monitoring:
                    print("📕 Book closed! Stopping monitoring...")
                    self.window.after(0, self.stop_monitoring)
                    self.window.after(0, lambda: self.status_label.config(foreground="red"))
                
                time.sleep(self.book_check_interval / 1000.0)
                
            except Exception as e:
                print(f"Book detection thread error: {e}")
                time.sleep(0.5)
    
    def start_book_detection(self):
        """Start the book detection thread"""
        self.book_detection_thread = threading.Thread(target=self.book_detection_loop, daemon=True)
        self.book_detection_thread.start()
    
    def capture_screen(self):
        """Capture the chest region"""
        try:
            screenshot = ImageGrab.grab(bbox=(self.x1, self.y1, self.x2, self.y2))
            screenshot_np = np.array(screenshot)
            screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            return screenshot_cv
        except Exception as e:
            print(f"Capture error: {e}")
            return None
    
    def detect_slots(self, img, threshold):
        """Detect chest slots in the captured image"""
        if img is None:
            return None, None, None
        
        try:
            output = img.copy()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            slots = []
            for contour in contours:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
                
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = w / float(h)
                    
                    if 0.7 < aspect_ratio < 1.3 and 10 < w < 150 and 10 < h < 150:
                        slots.append((x, y, w, h))
            
            slots = sorted(slots, key=lambda s: (s[1], s[0]))
            
            empty_count = 0
            filled_count = 0
            paper_detected_count = 0

            for i, (x, y, w, h) in enumerate(slots[:27]):
                slot_roi = img[y:y+h, x:x+w]
                
                if slot_roi.size == 0:
                    continue

                # --- NEW: First try paper template matching ---
                has_paper, confidence = self.detect_paper_in_slot(slot_roi, i)

                if has_paper:
                    # Paper found → empty slot
                    empty_count += 1
                    paper_detected_count += 1
                    cv2.rectangle(output, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    # Annotate with "P" + confidence percentage
                    label = f"P{int(confidence * 100)}"
                    cv2.putText(output, label, (x + 2, y + 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
                else:
                    # Fall back to intensity-based detection
                    std_intensity = np.std(slot_roi)
                    is_empty = std_intensity < threshold
                
                    if is_empty:
                        empty_count += 1
                        cv2.rectangle(output, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    else:
                        filled_count += 1
                        cv2.rectangle(output, (x, y), (x+w, y+h), (0, 0, 255), 2)

            # Periodic debug summary
            if self.debug_counter % 60 == 0:
                print(f"📊 Detection: {paper_detected_count} papers found, "
                      f"{empty_count} empty, {filled_count} filled")

            return empty_count, filled_count, output
            
        except Exception as e:
            print(f"Detection error: {e}")
            return None, None, None
    
    def start_monitoring(self):
        """Start live monitoring"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.canvas.delete(self.waiting_text)
            self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
            self.monitor_thread.start()
            print("🟢 Monitoring started!")
            if self.paper_template is None:
                print("⚠️  Paper template not loaded — falling back to intensity detection only")
    
    def stop_monitoring(self):
        """Stop live monitoring"""
        self.is_monitoring = False
        self.window.after(0, self.reset_display)
        print("🔴 Monitoring stopped!")
    
    def reset_display(self):
        """Reset display to blank/white screen"""
        self.canvas.delete("all")
        self.canvas.config(bg="#292929")
        
        capture_width = self.x2 - self.x1
        capture_height = self.y2 - self.y1
        display_width = int(capture_width * 0.5)
        display_height = int(capture_height * 0.5)
        
        self.waiting_text = self.canvas.create_text(
            display_width // 2, 
            display_height // 2,
            text="Waiting for book...",
            font=("Arial", 10),
            fill="gray"
        )
        
        self.empty_label.config(text="0")
        self.filled_label.config(text="0")
        self.total_label.config(text="0")
    
    def monitoring_loop(self):
        """Main monitoring loop that runs in background thread"""
        while self.is_monitoring:
            try:
                loop_start = time.time()
                
                img = self.capture_screen()
                
                if img is not None:
                    empty, filled, annotated = self.detect_slots(img, self.threshold)
                    
                    if annotated is not None:
                        self.window.after(0, self.update_display, empty, filled, annotated)
                
                loop_time = time.time() - loop_start
                sleep_time = max(0, (self.refresh_rate / 1000.0) - loop_time)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Monitoring loop error: {e}")
                time.sleep(0.1)
    
    def update_display(self, empty, filled, annotated_image):
        """Update GUI with new results"""
        self.empty_slots = empty
        self.filled_slots = filled
        
        self.empty_label.config(text=str(empty))
        self.filled_label.config(text=str(filled))
        total = empty + filled
        self.total_label.config(text=str(total))
        
        self.display_image(annotated_image)
    
    def display_image(self, cv_image):
        """Display OpenCV image on canvas"""
        try:
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
            
            capture_width = self.x2 - self.x1
            capture_height = self.y2 - self.y1
            display_width = int(capture_width * 0.5)
            display_height = int(capture_height * 0.5)
            
            pil_image = pil_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
            
            self.photo = ImageTk.PhotoImage(pil_image)
            
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            
        except Exception as e:
            print(f"Display error: {e}")
    
    def on_closing(self):
        """Handle window closing"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        self.window.destroy()


class InventoryDetector:
    """Simplified inventory detector for integration"""
    def __init__(self):
        self.x1 = 635
        self.y1 = 255
        self.x2 = 1283
        self.y2 = 473
        self.threshold = 20
        
        self.book_template = None
        
        self.load_templates()
    
    def load_templates(self):
        """Load book template"""
        try:
            self.book_template = cv2.imread('book.png', cv2.IMREAD_UNCHANGED)
            if self.book_template is None:
                print("⚠️ WARNING: book.png not found")
        except Exception as e:
            print(f"Error loading book.png: {e}")
    
    def detect_book_on_screen(self):
        """Detect if book.png is visible on screen"""
        if self.book_template is None:
            return False
        
        try:
            screenshot = ImageGrab.grab()
            screenshot_np = np.array(screenshot)
            screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            
            if len(self.book_template.shape) == 3 and self.book_template.shape[2] == 4:
                template_bgr = cv2.cvtColor(self.book_template, cv2.COLOR_BGRA2BGR)
            else:
                template_bgr = self.book_template
            
            result = cv2.matchTemplate(screenshot_cv, template_bgr, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            threshold = 0.8
            return max_val >= threshold
            
        except Exception as e:
            print(f"Book detection error: {e}")
            return False
    
    def capture_screen(self):
        """Capture the chest region"""
        try:
            screenshot = ImageGrab.grab(bbox=(self.x1, self.y1, self.x2, self.y2))
            screenshot_np = np.array(screenshot)
            screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            return screenshot_cv
        except Exception as e:
            print(f"Capture error: {e}")
            return None
    
    def detect_slots(self, img):
        """Detect chest slots and count empty ones"""
        if img is None:
            return 0
        
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            slots = []
            for contour in contours:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
                
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = w / float(h)
                    
                    if 0.7 < aspect_ratio < 1.3 and 10 < w < 150 and 10 < h < 150:
                        slots.append((x, y, w, h))
            
            slots = sorted(slots, key=lambda s: (s[1], s[0]))
            
            empty_count = 0
            
            for i, (x, y, w, h) in enumerate(slots[:27]):
                slot_roi = img[y:y+h, x:x+w]
                
                if slot_roi.size == 0:
                    continue
                
                std_intensity = np.std(slot_roi)
                is_empty = std_intensity < self.threshold
                if is_empty:
                    empty_count += 1
            
            return empty_count
            
        except Exception as e:
            print(f"Detection error: {e}")
            return 0
    
    def get_empty_slot_count(self):
        """Get the number of empty slots in the current chest"""
        img = self.capture_screen()
        return self.detect_slots(img)


class AutomatedAHBot:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto AH")
        self.root.geometry("330x290+1400+405")  # Reduced height since button removed
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        
        # Apply dark title bar
        apply_theme_to_titlebar(self.root)
        
        # Detectors
        self.detector = InventoryDetector()
        self.hotbar_detector = HotbarDetector()
        
        # Mouse controller for scrolling
        self.mouse = mouse.Controller()
        
        # Marked coordinates (27 slots)
        self.marked_coords = [
            (1250, 470), (1175, 470), (1100, 470), (1025, 470), (950, 470), 
            (875, 470), (800, 470), (725, 470), (650, 470),
            (1250, 400), (1175, 400), (1100, 400), (1025, 400), (950, 400),
            (875, 400), (800, 400), (725, 400), (650, 400),
            (1250, 330), (1175, 330), (1100, 330), (1025, 330), (950, 330),
            (875, 330), (800, 330), (725, 330), (650, 330)
        ]
        
        # Settings
        self.selected_order_option = tk.IntVar(value=1)
        self.sell_price = tk.StringVar(value="200k")
        self.running = False
        self.stop_requested = False
        
        # GUI windows - will be created automatically
        self.hotbar_gui = None
        self.chest_gui = None
        
        self.setup_ui()
        
        # Automatically show detector windows immediately
        self.auto_show_detector_windows()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_frame = ttk.Frame(self.root, padding="0")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=15, pady=(2, 15))
        style = ttk.Style()
        style.configure("TLabelframe.Label", font=("Arial", 10, "bold"))
        style.configure("TRadiobutton", font=("Arial", 10))
        style.configure("TEntry", font=("Arial", 10))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Order Option Selection
        option_frame = ttk.LabelFrame(main_frame, text="Order Option", padding="10")
        option_frame.grid(row=0, column=0, columnspan=2, pady=(0, 8), sticky=(tk.W, tk.E))
        option_frame.columnconfigure((0, 1, 2, 3), weight=1)
        
        # Horizontal layout for radio buttons
        ttk.Radiobutton(option_frame, text=" 1", 
                       variable=self.selected_order_option, value=1).grid(row=0, column=0, padx=5)
        ttk.Radiobutton(option_frame, text=" 2", 
                       variable=self.selected_order_option, value=2).grid(row=0, column=1, padx=5)
        ttk.Radiobutton(option_frame, text=" 3", 
                       variable=self.selected_order_option, value=3).grid(row=0, column=2, padx=5)
        ttk.Radiobutton(option_frame, text=" 4", 
                       variable=self.selected_order_option, value=4).grid(row=0, column=3, padx=5)
        
        # Sell Price
        price_frame = ttk.LabelFrame(main_frame, text="Sell Price", padding="10")
        price_frame.grid(row=1, column=0, columnspan=2, pady=(0, 8), sticky=(tk.W, tk.E))
        price_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(price_frame, textvariable=self.sell_price, width=20, 
                 font=("Arial", 10)).pack(fill=tk.X)
        
        # Status
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=2, column=0, columnspan=2, pady=(0, 8), sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="Ready to start", 
                                     font=("Arial", 10, "bold"))
        self.status_label.pack()
        
        self.progress_label = ttk.Label(status_frame, text="", 
                                       font=("Arial", 9), foreground="gray")
        self.progress_label.pack()
        
        # Control Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(4, 0), sticky=(tk.W, tk.E))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        self.start_button = ttk.Button(button_frame, text="Auto Pro (Ctrl+O)", 
                                      command=self.toggle_automation)
        self.start_button.grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))
        
        self.auto_sell_button = ttk.Button(button_frame, text="Auto OG  (Ctrl+P)", 
                                           command=self.start_auto_sell)
        self.auto_sell_button.grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))
        
        # Setup hotkeys
        try:
            keyboard.add_hotkey('ctrl+o', self.toggle_automation)
            keyboard.add_hotkey('ctrl+p', self.start_auto_sell)
            print("🔑 Hotkeys registered: Ctrl+O (Toggle Start/Stop), Ctrl+P (Auto Sell)")
        except Exception as e:
            print(f"Warning: Could not register hotkeys: {e}")
    
    def auto_show_detector_windows(self):
        """Automatically show the detector GUI windows on startup"""
        # Show hotbar detector
        if self.hotbar_gui is None or not tk.Toplevel.winfo_exists(self.hotbar_gui.window):
            self.hotbar_gui = HotbarDetectorGUI(self.root)
            self.hotbar_gui.window.protocol("WM_DELETE_WINDOW", self.hotbar_gui.on_closing)
        
        # Show chest detector
        if self.chest_gui is None or not tk.Toplevel.winfo_exists(self.chest_gui.window):
            self.chest_gui = ChestDetectorGUI(self.root)
            self.chest_gui.window.protocol("WM_DELETE_WINDOW", self.chest_gui.on_closing)
        
        print("✅ Detector windows opened automatically")
    
    def update_status(self, message, progress=""):
        """Update status labels"""
        self.status_label.config(text=message)
        self.progress_label.config(text=progress)
        self.root.update()
    
    def toggle_automation(self):
        """Toggle start/stop of the main automation"""
        if self.running:
            self.stop_automation()
        else:
            self.start_automation()

    def start_automation(self):
        """Start the automation process"""
        if self.running:
            return
        
        self.running = True
        self.stop_requested = False
        self.start_button.config(text="Stop (Ctrl+O)")
        self.auto_sell_button.config(state=tk.DISABLED)
        
        # Run automation in separate thread
        automation_thread = threading.Thread(target=self.run_automation, daemon=True)
        automation_thread.start()
    
    def stop_automation(self):
        """Stop the automation"""
        if self.running:
            self.stop_requested = True
            self.update_status("⏹️ Stopping...", "Please wait")
    
    def wait_for_hotbar_block(self):
        """Wait until hotbar has a block, scrolling if needed"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            has_block, variance = self.hotbar_detector.check_current_slot()
            
            if has_block:
                print(f"✅ Block detected in hotbar (variance: {variance:.2f})")
                return True
            else:
                print(f"⚠️ No block in hotbar (variance: {variance:.2f}), scrolling up...")
                self.mouse.scroll(0, 1)  # Scroll up once
                time.sleep(0.3)  # Wait for scroll to complete
                attempt += 1
        
        print(f"❌ Failed to find block in hotbar after {max_attempts} attempts")
        return False
    
    def run_automation(self):
        """Main automation logic"""
        try:
            self.update_status("Starting automation...", "Preparing")
            time.sleep(1)
            
            # Step 1: Type /ah and press enter
            self.update_status("Opening Auction House", "Step 1/8")
            pyautogui.press('t')
            time.sleep(0.3)
            pyautogui.write('/ah', interval=0.05)
            pyautogui.press('enter')
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Step 2: Click on coordinate (1100, 540)
            self.update_status("Navigating AH menu", "Step 2/8")
            pyautogui.click(1100, 540, duration=0.3)
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Step 3: Detect empty slots
            self.update_status("Detecting inventory", "Step 3/8")
            time.sleep(0.5)
            
            # Wait for inventory to be visible
            max_wait = 5
            wait_count = 0
            while wait_count < max_wait:
                if self.detector.detect_book_on_screen():
                    break
                time.sleep(0.5)
                wait_count += 0.5
            
            empty_slots = self.detector.get_empty_slot_count()
            self.update_status(f"Detected {empty_slots} empty slots", "Step 3/8")
            time.sleep(1)
            
            if empty_slots == 0:
                self.update_status("No empty slots detected!", "Stopping")
                self.cleanup()
                return
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Step 4: Press E twice
            self.update_status("Closing inventory", "Step 4/8")
            pyautogui.press('e')
            time.sleep(0.3)
            pyautogui.press('e')
            time.sleep(1)
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Step 5: Type /order and press enter
            self.update_status("Opening orders", "Step 5/8")
            pyautogui.press('t')
            time.sleep(0.3)
            pyautogui.write('/order', interval=0.05)
            pyautogui.press('enter')
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Step 6: Click on selected order option
            order_coords = {
                1: (670, 300),
                2: (740, 300),
                3: (810, 300),
                4: (880, 300)
            }
            selected_coord = order_coords[self.selected_order_option.get()]
            self.update_status(f"Selecting order option {self.selected_order_option.get()}", "Step 6/8")
            pyautogui.click(1100, 540, duration=0.3)
            time.sleep(0.5)
            
            # Move to the order option coordinate
            pyautogui.moveTo(selected_coord[0], selected_coord[1], duration=0.5)
            
            # Click the order option
            pyautogui.click(duration=0.3)
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Step 7: Click on (960, 360)
            self.update_status("Confirming order", "Step 7/8")
            pyautogui.click(960, 360, duration=0.3)
            time.sleep(0.5)
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Step 8: Hold shift and click marked coordinates
            self.update_status(f"Collecting items (0/{empty_slots})", "Step 8/8")

            # Press and HOLD shift at the start
            pyautogui.keyDown('shift')
            time.sleep(0.1)  # Small delay to ensure shift is registered
            
            for i in range(empty_slots):
                if self.stop_requested:
                    pyautogui.keyUp('shift')
                    self.cleanup()
                    return
                
                # Add delay before clicking the 10th coordinate (index 9)
                if i == 9 and empty_slots > 9:
                    self.update_status(f"Collecting items ({i}/{empty_slots})", "Waiting before row 2...")
                    time.sleep(0.5)
                
                # Add delay before clicking the 19th coordinate (index 18)
                if i == 18 and empty_slots > 18:
                    self.update_status(f"Collecting items ({i}/{empty_slots})", "Waiting before row 3...")
                    time.sleep(0.5)
                
                coord = self.marked_coords[i]
                pyautogui.click(coord[0], coord[1], duration=0.3)
                
                self.update_status(f"Collecting items ({i+1}/{empty_slots})", "Step 8/8")
            
            # Release shift after ALL items collected
            pyautogui.keyUp('shift')
            time.sleep(0.2)
            
            if self.stop_requested:
                self.cleanup()
                return
            
            # Close order menu
            pyautogui.press('e')
            time.sleep(1)
            
            # Step 9: Perform sell actions (combined with hotbar restocking and hotbar detection)
            self.update_status("Selling items", f"0/{empty_slots} sold")
            
            sell_command = f"/ah sell {self.sell_price.get()}"
            pyperclip.copy(sell_command)
            
            for i in range(empty_slots):
                if self.stop_requested:
                    self.cleanup()
                    return
                
                # Check hotbar before selling (NEW FEATURE)
                self.update_status("Checking hotbar...", f"{i}/{empty_slots} sold")
                if not self.wait_for_hotbar_block():
                    self.update_status("❌ Could not find block in hotbar", "Stopped")
                    self.cleanup()
                    return
                
                # Press 't' and paste command
                pyautogui.press('t')
                pyautogui.hotkey('ctrl', 'v')
                pyautogui.press('enter')
                pyautogui.click(1101, 364, duration=0.3)
                self.mouse.scroll(0, 1)
                
                self.update_status("Selling items", f"{i+1}/{empty_slots} sold")
                
                # After selling 9 items (index 8) and there are more than 9 items total
                if i == 8 and empty_slots > 9:
                    self.update_status("Restocking hotbar (1st restock)...", "")
                    
                    y_coord = 700
                    
                    # Restock sequence
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
                    
                    self.update_status("Hotbar restocked (1/2)", "Continuing sales...")
                
                # After selling 18 items (index 17) and there are more than 18 items total
                elif i == 17 and empty_slots > 18:
                    self.update_status("Restocking hotbar (2nd restock)...", "")
                    
                    y_coord = 650
                    
                    # Restock sequence
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
                    
                    self.update_status("Hotbar restocked (2/2)", "Continuing sales...")
            
            # Complete
            self.update_status("✅ Automation complete!", f"Sold {empty_slots} items")
            time.sleep(2)
            
            self.cleanup()
            
        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}", "Stopped")
            print(f"Automation error: {e}")
            self.cleanup()
    
    def cleanup(self):
        """Clean up after automation"""
        self.running = False
        self.stop_requested = False
        self.start_button.config(text="Auto Pro (Ctrl+O)")
        self.auto_sell_button.config(state=tk.NORMAL)
        
        if not self.status_label.cget("text").startswith("✅"):
            self.update_status("Ready to start", "")
    
    def start_auto_sell(self):
        """Start the auto sell routine from auto.py logic"""
        if self.running or getattr(self, '_auto_sell_running', False):
            return
        
        self._auto_sell_running = True
        self._auto_sell_stop = False
        self.auto_sell_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self._run_auto_sell, daemon=True)
        thread.start()

    def _run_auto_sell(self):
        """Auto sell logic ported from auto.py - uses sell_price from this UI"""
        try:
            mouse_ctrl = mouse.Controller()
            
            # Copy the sell command using the sell_price from this UI
            sell_value = self.sell_price.get()
            sell_command = f"/ah sell {sell_value}"
            pyperclip.copy(sell_command)
            
            y_coordinates = [700, 650, 550]
            
            for set_idx in range(3):
                if self._auto_sell_stop:
                    break
                
                y_coord = y_coordinates[set_idx]
                self.update_status(f"Auto Sell: Drag Y:{y_coord}", f"Set {set_idx+1}/3")
                
                # Drag sequence
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
                except Exception:
                    try:
                        pyautogui.keyUp('shift')
                    except Exception:
                        pass
                
                if self._auto_sell_stop:
                    break
                
                self.update_status("Auto Sell: Waiting...", f"Set {set_idx+1}/3")
                time.sleep(1.0)
                
                if self._auto_sell_stop:
                    break
                
                # Inner sell loop (9 items per set)
                for loop_idx in range(9):
                    if self._auto_sell_stop:
                        break
                    
                    self.update_status(f"Auto Sell: Selling", f"Set {set_idx+1}/3 - Item {loop_idx+1}/9")
                    pyautogui.press('t')
                    pyautogui.hotkey('ctrl', 'v')
                    pyautogui.press('enter')
                    pyautogui.click(1101, 364, duration=0.3)
                    mouse_ctrl.scroll(0, 1)
            
            if not self._auto_sell_stop:
                self.update_status("✅ Auto Sell complete!", "27 items sold")
                time.sleep(2)
        
        except Exception as e:
            self.update_status(f"❌ Auto Sell Error: {str(e)}", "")
        
        finally:
            self._auto_sell_running = False
            self._auto_sell_stop = False
            self.auto_sell_button.config(state=tk.NORMAL)
            self.start_button.config(state=tk.NORMAL)
            if not self.status_label.cget("text").startswith("✅"):
                self.update_status("Ready to start", "")

    def on_closing(self):
        """Handle window closing"""
        try:
            keyboard.unhook_all_hotkeys()
            print("🔴 Global hotkeys removed")
        except:
            pass
        
        # Close detector windows
        if self.hotbar_gui and tk.Toplevel.winfo_exists(self.hotbar_gui.window):
            self.hotbar_gui.on_closing()
        if self.chest_gui and tk.Toplevel.winfo_exists(self.chest_gui.window):
            self.chest_gui.on_closing()
        
        self.root.destroy()


def main():
    # Set PyAutoGUI settings
    pyautogui.PAUSE = 0.1
    pyautogui.FAILSAFE = True
    
    root = tk.Tk()
    
    # Apply Sun Valley theme
    sv_ttk.set_theme("dark")
    
    app = AutomatedAHBot(root)
    
    # Handle window close event
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()


if __name__ == "__main__":
    main()

