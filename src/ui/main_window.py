from PyQt5.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget
from ui.home_page.home_page import HomeScreen

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLS Camera Feed")
        self.setGeometry(100, 100, 400, 600)
        self.setStyleSheet("background-color: red;")  # Set the background color to red
        self.home_screen = HomeScreen(self)
        self.setCentralWidget(self.home_screen)