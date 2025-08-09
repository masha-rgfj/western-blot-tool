# src/main.py

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QFileDialog, QInputDialog, QWidget, QVBoxLayout,
    QGraphicsLineItem, QGraphicsSimpleTextItem
)
from PySide6.QtGui import QAction, QPixmap, QPen, QFont
from PySide6.QtCore import Qt, QRect, QSize, QPoint, QPointF


class CanvasView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rubberBand = None
        self.origin = QPoint()
        self.mode = None            # None | "crop" | "mark"
        self.crop_callback = None
        self.mark_callback = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.mode == "crop" and self.crop_callback:
            from PySide6.QtWidgets import QRubberBand  # avoid global import clash
            self.origin = event.pos()
            if self.rubberBand is None:
                self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()
        elif event.button() == Qt.LeftButton and self.mode == "mark" and self.mark_callback:
            scene_pt = self.mapToScene(event.pos())
            self.mark_callback(scene_pt.y())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.rubberBand and self.rubberBand.isVisible():
            rect = QRect(self.origin, event.pos()).normalized()
            self.rubberBand.setGeometry(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.rubberBand and self.rubberBand.isVisible():
            self.rubberBand.hide()
            rect = QRect(self.origin, event.pos()).normalized()
            scene_rect = self.mapToScene(rect).boundingRect().toRect()
            if self.crop_callback:
                self.crop_callback(scene_rect)
            # one-shot crop unless re-enabled
            self.mode = None
        else:
            super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Western Blot Figure Tool")

        self.current_pixmap = None
        self.pixmap_item = None

        # store kDa markers: list of dicts {y: float, kda: float, line: QGraphicsLineItem, text: QGraphicsSimpleTextItem}
        self.kda_markers = []

        # Scene/View
        self.scene = QGraphicsScene(self)
        self.view = CanvasView(self)
        self.view.setScene(self.scene)
        self.view.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.view)

        # Menus
        file_menu = self.menuBar().addMenu("File")
        open_action = QAction("Open Image…", self)
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)

        tools_menu = self.menuBar().addMenu("Tools")
        mark_action = QAction("Mark kDa Bands", self)
        mark_action.triggered.connect(self.enable_mark_mode)
        tools_menu.addAction(mark_action)

        undo_mark_action = QAction("Undo Last kDa", self)
        undo_mark_action.triggered.connect(self.undo_last_kda)
        tools_menu.addAction(undo_mark_action)

        clear_marks_action = QAction("Clear All kDa", self)
        clear_marks_action.triggered.connect(self.clear_all_kda)
        tools_menu.addAction(clear_marks_action)

        crop_action = QAction("Crop Region", self)
        crop_action.triggered.connect(self.enable_crop_mode)
        tools_menu.addAction(crop_action)

    # ------------ Image I/O ------------
    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Gel Image", "", "Image Files (*.png *.jpg *.jpeg *.tif *.tiff)"
        )
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return

        self.current_pixmap = pixmap
        self.scene.clear()
        self.kda_markers.clear()
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.view.setSceneRect(pixmap.rect())
        self.view.fitInView(pixmap.rect(), Qt.KeepAspectRatio)

    # ------------ kDa marking ------------
    def enable_mark_mode(self):
        if self.current_pixmap is None:
            return
        self.view.mode = "mark"
        self.view.mark_callback = self.add_kda_marker

    def add_kda_marker(self, scene_y: float):
        # Ask user for kDa value
        val, ok = QInputDialog.getDouble(self, "kDa value", "Enter kDa:", decimals=1, minValue=0.0, maxValue=1e6)
        if not ok:
            return

        # Draw tick line + text at left edge of image
        if self.pixmap_item is None:
            return
        img_left = self.pixmap_item.sceneBoundingRect().left()
        x0 = img_left
        x1 = img_left + 20.0

        pen = QPen(Qt.black)
        line_item = QGraphicsLineItem(x0, scene_y, x1, scene_y)
        line_item.setPen(pen)
        self.scene.addItem(line_item)

        label = QGraphicsSimpleTextItem(f"{val:g}")
        label.setFont(QFont("", 10))
        label.setBrush(Qt.black)
        label.setPos(x1 + 6.0, scene_y - 8.0)
        self.scene.addItem(label)

        self.kda_markers.append({"y": float(scene_y), "kda": float(val), "line": line_item, "text": label})
        # keep them sorted (optional)
        self.kda_markers.sort(key=lambda d: d["y"])

    def undo_last_kda(self):
        if not self.kda_markers:
            return
        last = self.kda_markers.pop()
        self.scene.removeItem(last["line"])
        self.scene.removeItem(last["text"])

    def clear_all_kda(self):
        for d in self.kda_markers:
            self.scene.removeItem(d["line"])
            self.scene.removeItem(d["text"])
        self.kda_markers.clear()

    # ------------ Cropping ------------
    def enable_crop_mode(self):
        if self.current_pixmap is None:
            return
        self.view.mode = "crop"
        self.view.crop_callback = self.crop_region

    def crop_region(self, scene_rect):
        # Copy the pixels from the source pixmap
        cropped = self.current_pixmap.copy(scene_rect)
        # filter kDa markers that fall inside this rect
        inside = [m for m in self.kda_markers if scene_rect.top() <= m["y"] <= scene_rect.bottom()]
        # Show preview with ticks re-drawn relative to crop top
        self.show_cropped_with_ticks(cropped, inside, scene_rect)

    def show_cropped_with_ticks(self, pixmap: QPixmap, markers, src_rect):
        # Simple preview window built on QGraphicsScene so we can draw ticks too
        w = QWidget()
        w.setWindowTitle("Cropped Region (with kDa)")
        layout = QVBoxLayout(w)
        preview_scene = QGraphicsScene(w)
        preview_view = QGraphicsView(preview_scene)
        layout.addWidget(preview_view)

        pix_item = preview_scene.addPixmap(pixmap)
        preview_view.setSceneRect(pixmap.rect())

        # draw ticks/labels relative to crop
        pen = QPen(Qt.black)
        for m in markers:
            y_local = m["y"] - src_rect.top()
            x0 = 0.0
            x1 = 20.0
            line = QGraphicsLineItem(x0, y_local, x1, y_local)
            line.setPen(pen)
            preview_scene.addItem(line)

            label = QGraphicsSimpleTextItem(f"{m['kda']:g}")
            label.setFont(QFont("", 10))
            label.setBrush(Qt.black)
            label.setPos(x1 + 6.0, y_local - 8.0)
            preview_scene.addItem(label)

        w.resize(500, 400)
        w.show()
        # keep reference
        self._crop_window = w


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 700)
    win.show()
    sys.exit(app.exec())
