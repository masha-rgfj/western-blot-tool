import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QFileDialog
)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Western Blot Tool")
        self.resize(800, 600)
        self._create_actions()
        self._create_menu()
        self._create_graphics_view()

    def _create_actions(self): #setting up the menu
        self.open_act = QAction("&Open Image...", self)
        self.open_act.triggered.connect(self.open_image)

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.open_act)

    def _create_graphics_view(self):
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setCentralWidget(self.view)

    def open_image(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Open Gel Image", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff)"
        )
        if fname:
            pixmap = QPixmap(fname)
            self.scene.clear()
            self.scene.addPixmap(pixmap)
            self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
