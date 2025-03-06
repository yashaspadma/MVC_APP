import sys
import os
import signal
import logging
import threading
import numpy as np
import cv2 as cv
from flask import Flask, Response
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QThread, pyqtSignal
from senxor.mi48 import MI48, format_header, format_framestats
from senxor.utils import data_to_frame, remap, cv_filter, RollingAverageFilter, connect_senxor

# Enable logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class ThermalCamera(QThread):
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, roi=(0, 0, 61, 61), com_port=None):
        super().__init__()
        self.roi = roi
        self.com_port = com_port
        self.running = True
        self.latest_frame = None
        self.lock = threading.Lock()

        self.temps = {"Top": 0, "Bottom": 0, "Left": 0, "Right": 0, "Center": 0}

        self.mi48, self.connected_port, _ = connect_senxor(src=self.com_port) if self.com_port else connect_senxor()

        logger.info(f"Camera initialized on {self.connected_port}")

        self.mi48.set_fps(25)
        self.mi48.disable_filter(f1=True, f2=True, f3=True)
        self.mi48.set_filter_1(85)
        self.mi48.enable_filter(f1=True, f2=False, f3=False, f3_ks_5=False)
        self.mi48.set_offset_corr(0.0)
        self.mi48.set_sens_factor(100)
        self.mi48.start(stream=True, with_header=True)

        self.dminav = RollingAverageFilter(N=10)
        self.dmaxav = RollingAverageFilter(N=10)

    def run(self):
        while self.running:
            self.process_frame()

    def process_frame(self):
        data, header = self.mi48.read()
        if data is None:
            logger.error("No data received from the camera.")
            return

        min_temp = self.dminav(data.min())
        max_temp = self.dmaxav(data.max())

        frame = data_to_frame(data, (80, 62), hflip=True)
        frame = np.clip(frame, min_temp, max_temp)
        frame = cv.flip(frame, 1)
        frame = cv.rotate(frame, cv.ROTATE_90_CLOCKWISE)

        filt_frame = cv_filter(remap(frame), {'blur_ks': 3, 'd': 5, 'sigmaColor': 27, 'sigmaSpace': 27}, use_median=True, use_bilat=True, use_nlm=False)

        x1, y1, x2, y2 = self.roi
        roi_frame = filt_frame[y1:y2, x1:x2]
        roi_frame = cv.applyColorMap(roi_frame, cv.COLORMAP_INFERNO)
        self.draw_grid(roi_frame)
        roi_frame = cv.resize(roi_frame, (600, 600), interpolation=cv.INTER_LINEAR)

        temps = self.calculate_temperatures(frame, x1, y1, x2, y2)
        self.overlay_text(roi_frame, temps)

        with self.lock:
            self.latest_frame = roi_frame

        self.frame_ready.emit(roi_frame)

    def draw_grid(self, frame):
        h, w = frame.shape[:2]
        step_w, step_h = w // 3, h // 3
        dot_length = 6
        dot_gap = 12

        for i in range(1, 3):
            x = i * step_w
            for y in range(0, h, dot_length + dot_gap):
                cv.line(frame, (x, y), (x, min(y + dot_length, h)), (255, 255, 255), 1)

        for i in range(1, 3):
            y = i * step_h
            for x in range(0, w, dot_length + dot_gap):
                cv.line(frame, (x, y), (min(x + dot_length, w), y), (255, 255, 255), 1)

    def calculate_temperatures(self, frame, x1, y1, x2, y2):
        w, h = x2 - x1, y2 - y1
        section_w, section_h = w // 3, h // 3

        sections = {
            "Top": frame[y1:y1+section_h, x1:x2],
            "Bottom": frame[y2-section_h:y2, x1:x2],
            "Left": frame[y1:y2, x1:x1+section_w],
            "Right": frame[y1:y2, x2-section_w:x2],
            "Center": frame[y1+section_h:y2-section_h, x1+section_w:x2-section_w]
        }

        self.temps = {name: np.mean(region) for name, region in sections.items()}
        return self.temps

    def overlay_text(self, frame, temps):
        h, w = frame.shape[:2]
        section_w, section_h = w // 3, h // 3

        positions = {
            "Top": (w // 2 - 50, section_h // 2),
            "Bottom": (w // 2 - 50, h - section_h // 2),
            "Left": (section_w // 4, h // 2),
            "Right": (w - section_w // 2 - 50, h // 2),
            "Center": (w // 2 - 50, h // 2)
        }

        for section, temp in temps.items():
            x, y = positions[section]
            cv.putText(frame, f"{temp:.2f}C", (x, y), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1)

    def start_stream(self):
        app = Flask(__name__)

        @app.route('/video_feed')
        def video_feed():
            return Response(self.generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

        threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False), daemon=True).start()

    def generate_frames(self):
        while self.running:
            with self.lock:
                if self.latest_frame is None:
                    continue
                
                _, buffer = cv.imencode('.jpg', self.latest_frame)
                frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    def stop(self):
        self.running = False
        self.mi48.stop()
        cv.destroyAllWindows()

class ThermalCam(QWidget):
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.thermal_camera = ThermalCamera()
        self.thermal_camera.start()
        self.thermal_camera.start_stream()
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.label = QLabel("Thermal Cam Feed is available on the web at http://localhost:5000/video_feed")
        self.layout.addWidget(self.label)

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        self.layout.addWidget(self.back_button)

        self.setLayout(self.layout)

    def go_back(self):
        self.thermal_camera.stop()
        self.main_window.setCentralWidget(self.main_window.home_screen)

    def closeEvent(self, event):
        self.thermal_camera.stop()
        event.accept()

# **Main Execution**
if __name__ == "__main__":
    roi = (0, 0, 61, 61)
    cam = ThermalCamera(roi=roi, com_port=None)
    cam.start_stream()
