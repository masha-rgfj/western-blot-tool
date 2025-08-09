# src/main.py

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QFileDialog, QInputDialog, QWidget, QVBoxLayout,
    QGraphicsLineItem, QGraphicsSimpleTextItem,
    QGraphicsTextItem, QGraphicsRectItem
)
from PySide6.QtGui import QAction, QPixmap, QPen, QFont, QColor
from PySide6.QtCore import Qt, QRect, QSize, QPoint, QPointF, QRectF





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
            from PySide6.QtWidgets import QRubberBand
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
            self.mode = None
        else:
            super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Western Blot Figure Tool")

        self.current_pixmap = None
        self.pixmap_item = None
        self.kda_markers = []

        # margin (px) to the LEFT of the gel for ticks/labels
        self.left_margin = 60

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
        
        #show instructions before any image is loaded
        self.show_startup_message()
        
    def show_startup_message(self):
        """Display initial instructions in the scene."""
        self.scene.clear()
        self.kda_markers.clear()
        self.pixmap_item = None

        # give the empty scene a reasonable size to center the message
        W, H = 1000, 700
        self.scene.setSceneRect(0, 0, W, H)

        html = """
    <div style="color:#444; font-family:Segoe UI, Arial, Helvetica;">
      <h2 style="margin:0">Western Blot Figure Tool</h2>
      <p style="margin:8px 0 0 0">
        Please <b>pre-rotate</b> your gel so bands run <b>horizontally</b>.
      </p>
      <ul style="margin:6px 0 0 18px">
        <li>File → <i>Open Image…</i></li>
        <li>Tools → <i>Mark kDa Bands</i> (click ladder, enter values)</li>
        <li>Tools → <i>Crop Region</i> (ticks are drawn outside on the left)</li>
      </ul>
    </div>
    """

        msg = QGraphicsTextItem()
        msg.setTextWidth(520)          # set width first so wrapping is correct
        msg.setHtml(html)              # render as rich text (no literal <b>…</b>)

        br = msg.boundingRect()        # now measure after textWidth/html set
        msg.setPos((W - br.width())/2, (H - br.height())/2)

    # soft background panel
        from PySide6.QtGui import QColor, QPen
        from PySide6.QtWidgets import QGraphicsRectItem
        pad = 12
        bg = QGraphicsRectItem(0, 0, br.width()+2*pad, br.height()+2*pad)
        bg.setBrush(QColor(245, 245, 245))
        bg.setPen(QPen(Qt.lightGray))
        bg.setPos(msg.x()-pad, msg.y()-pad)
        bg.setZValue(-1)

        self.scene.addItem(bg)
        self.scene.addItem(msg)

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

        # place the pixmap shifted to the RIGHT by left_margin
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.pixmap_item.setPos(self.left_margin, 0)

        # extend scene rect so margin area is visible
        self.scene.setSceneRect(QRectF(0, 0, pixmap.width() + self.left_margin + 10, pixmap.height()))
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    # ------------ kDa marking ------------
    def enable_mark_mode(self):
        if self.current_pixmap is None:
            return
        self.view.mode = "mark"
        self.view.mark_callback = self.add_kda_marker

    def add_kda_marker(self, scene_y: float):
        # Ask user for kDa value (positional args)
        val, ok = QInputDialog.getDouble(self, "kDa value", "Enter kDa:", 0.0, 0.0, 1_000_000.0, 1)
        if not ok or self.pixmap_item is None:
            return

        # draw tick just LEFT of gel, inside the margin
        x1 = self.left_margin - 2.0   # near gel edge
        x0 = x1 - 20.0                # tick length 20 px to the left

        pen = QPen(Qt.black)
        line_item = QGraphicsLineItem(x0, scene_y, x1, scene_y)
        line_item.setPen(pen)
        self.scene.addItem(line_item)

        # label to the left of the tick
        label = QGraphicsSimpleTextItem(f"{val:g}")
        label.setFont(QFont("", 10))
        label.setBrush(Qt.black)
        
        br = label.boundingRect()
        gap = 6.0  # space between label and tick
        label_x = x0 - gap - br.width()         # x0 is the LEFT end of the tick
        label_y = scene_y - br.height() / 2.0   # vertically center
        label.setPos(label_x, label_y)
        self.scene.addItem(label)

        self.kda_markers.append({"y": float(scene_y), "kda": float(val), "line": line_item, "text": label})
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
        # convert scene rect to PIXMAP coordinates (because pixmap is shifted by left_margin)
        offset = self.pixmap_item.pos().toPoint()  # (left_margin, 0)
        pix_rect = scene_rect.translated(-offset)
        cropped = self.current_pixmap.copy(pix_rect)

        # keep only markers whose y falls inside the crop's scene rect
        inside = [m for m in self.kda_markers if scene_rect.top() <= m["y"] <= scene_rect.bottom()]

        self.show_cropped_with_ticks(cropped, inside, scene_rect)

    def show_cropped_with_ticks(self, pixmap: QPixmap, markers, src_scene_rect):
        # preview with its own left margin so ticks are outside the crop
        left_margin = 60

        w = QWidget()
        w.setWindowTitle("Cropped Region (with kDa)")
        layout = QVBoxLayout(w)
        preview_scene = QGraphicsScene(w)
        preview_view = QGraphicsView(preview_scene)
        layout.addWidget(preview_view)

        # place crop at (left_margin, 0)
        pix_item = preview_scene.addPixmap(pixmap)
        pix_item.setPos(left_margin, 0)

        # extend scene
        preview_scene.setSceneRect(QRectF(0, 0, pixmap.width() + left_margin + 10, pixmap.height()))

        # draw ticks in the margin
        pen = QPen(Qt.black)
        for m in markers:
            y_local = m["y"] - src_scene_rect.top()
            x1 = left_margin - 2.0
            x0 = x1 - 20.0
            line = QGraphicsLineItem(x0, y_local, x1, y_local)
            line.setPen(pen)
            preview_scene.addItem(line)

            label = QGraphicsSimpleTextItem(f"{m['kda']:g}")
            label.setFont(QFont("", 10))
            label.setBrush(Qt.black)
            br = label.boundingRect()
            label.setPos(x0 - 6.0 - br.width(), y_local - br.height()/2.0)
            preview_scene.addItem(label)

        w.resize(600, 450)
        w.show()
        self._crop_window = w


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1000, 750)
    win.show()
    sys.exit(app.exec())
