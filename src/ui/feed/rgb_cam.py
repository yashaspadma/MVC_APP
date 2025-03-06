import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import numpy as np
import time

class RGBCamera(QThread):
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.running = True
        self.cap = cv2.VideoCapture(0)

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("Error: Failed to capture an image.")
                time.sleep(0.5)  # Add a small delay before retrying
                continue

            # Convert frame to grayscale (if needed)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Emit the frame
            self.frame_ready.emit(gray)

    def stop(self):
        self.running = False
        self.cap.release()
        cv2.destroyAllWindows()

class RGBCam(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rgb_camera = RGBCamera()
        self.rgb_camera.frame_ready.connect(self.update_frame)
        self.rgb_camera.start()
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.label = QLabel("RGB Cam Feed")
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)

    def update_frame(self, frame):
        image = QImage(frame, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format_Grayscale8)
        self.label.setPixmap(QPixmap.fromImage(image))

    def closeEvent(self, event):
        self.rgb_camera.stop()
        event.accept()
