from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QSize
from ui.feed.thermal_cam import ThermalCam
from ui.feed.rgb_cam import RGBCam

class HomeScreen(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("SLS Camera Feed")
        self.setGeometry(100, 100, 400, 300)  # Set the window size to 400x300 (x,y width x height)
        self.setStyleSheet("background-color: red;")  # Set the background color to red
        
        layout = QVBoxLayout()
        button_layout = QVBoxLayout()

        self.rgb_button = QPushButton("RGB Feed")
        self.thermal_button = QPushButton("Thermal Feed")
        self.serial_button = QPushButton("Heater Control")

        # Make the buttons square
        button_size = QSize(200, 200)
        self.rgb_button.setFixedSize(button_size)
        self.thermal_button.setFixedSize(button_size)
        self.serial_button.setFixedSize(button_size)

        # Change button colors
        self.rgb_button.setStyleSheet("background-color: grey; color: black;")
        self.thermal_button.setStyleSheet("background-color: grey; color: black;")
        self.serial_button.setStyleSheet("background-color: grey; color: black;")

        layout.addWidget(self.rgb_button)
        layout.addWidget(self.thermal_button)
        layout.addWidget(self.serial_button)

        self.setLayout(layout)

        # Connect buttons to their respective methods
        self.rgb_button.clicked.connect(self.show_rgb_cam)
        self.thermal_button.clicked.connect(self.show_thermal_cam)
        self.serial_button.clicked.connect(self.show_heater_control)

    def show_thermal_cam(self):
        print("Thermal feed button clicked")
        self.main_window.switch_screen(ThermalCam(self.main_window, self.main_window))

    def show_rgb_cam(self):
        print("RGB feed button clicked")
        self.main_window.switch_screen(RGBCam(self.main_window))

    def show_heater_control(self):
        print("Heater Control button clicked")
        # self.main_window.switch_screen(HeaterControl(self.main_window))