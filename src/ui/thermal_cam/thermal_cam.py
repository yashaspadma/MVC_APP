import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import numpy as np
from flask import Flask, Response
from senxor.mi48 import MI48, format_header, format_framestats
from senxor.utils import data_to_frame, remap, cv_filter, RollingAverageFilter, connect_senxor
import threading
import logging

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
        frame = cv2.flip(frame, 1)
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

        filt_frame = cv_filter(remap(frame), {'blur_ks': 3, 'd': 5, 'sigmaColor': 27, 'sigmaSpace': 27}, use_median=True, use_bilat=True, use_nlm=False)

        x1, y1, x2, y2 = self.roi
        roi_frame = filt_frame[y1:y2, x1:x2]
        roi_frame = cv2.applyColorMap(roi_frame, cv2.COLORMAP_INFERNO)
        self.draw_grid(roi_frame)
        roi_frame = cv2.resize(roi_frame, (600, 600), interpolation=cv2.INTER_LINEAR)

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
                cv2.line(frame, (x, y), (x, min(y + dot_length, h)), (255, 255, 255), 1)

        for i in range(1, 3):
            y = i * step_h
            for x in range(0, w, dot_length + dot_gap):
                cv2.line(frame, (x, y), (min(x + dot_length, w), y), (255, 255, 255), 1)

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
            cv2.putText(frame, f"{temp:.2f}C", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1)

    def stop(self):
        self.running = False
        self.mi48.stop()
        cv2.destroyAllWindows()

class ThermalCam(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.thermal_camera = ThermalCamera()
        self.thermal_camera.frame_ready.connect(self.update_frame)
        self.thermal_camera.start()
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.label = QLabel("Thermal Cam Feed")
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)

    def update_frame(self, frame):
        image = QImage(frame, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(image))

    def closeEvent(self, event):
        self.thermal_camera.stop()
        event.accept()