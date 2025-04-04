# plot_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg
import numpy as np
from PyQt5.QtGui import QPainter, QLinearGradient, QColor, QFont, QPen
from PyQt5.QtCore import Qt
from pyqtgraph.Qt import QtCore

class FieldPlotWidget(pg.GraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_item = pg.PlotItem()
        self.setCentralItem(self.plot_item)
        
        # Lock aspect ratio to 1:1
        self.plot_item.setAspectLocked(True, ratio=1)
        
        self.scatter = pg.ScatterPlotItem()
        self.plot_item.addItem(self.scatter)
        # Tractor marker as an arrow (rotatable)
        self.tractor_marker = pg.ArrowItem(angle=0, tipAngle=45, baseAngle=25, headLen=40, tailLen=0, tailWidth=0, brush='g')
        self.plot_item.addItem(self.tractor_marker)
    
    def update_points(self, points):
        if not points:
            return
        xs = np.array([p["x"] for p in points])
        ys = np.array([p["y"] for p in points])
        zs = np.array([p["z"] for p in points])
        
        # Normalize z values to [0, 1]
        if np.ptp(zs) > 0:  # Check if there's any variation in z
            norm = (zs - np.min(zs)) / np.ptp(zs)
        else:
            norm = np.zeros_like(zs)
        
        # Create blue to red color gradient
        colors = []
        for val in norm:
            r = int(255 * val)
            g = 0
            b = int(255 * (1 - val))
            colors.append(pg.mkBrush(r, g, b))
        
        spots = [{'pos': (x, y), 'data': 1, 'brush': color} for x, y, color in zip(xs, ys, colors)]
        self.scatter.setData(spots)
        
        # Make sure to re-apply the aspect lock after updates, if needed
        self.plot_item.setAspectLocked(True, ratio=1)
    
    def update_tractor(self, x, y, heading=0):
        # Update position and orientation of the arrow marker.
        self.tractor_marker.setPos(x, y)
        self.tractor_marker.setRotation(heading+90)

class LevelingPlotWidget(pg.GraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_item = pg.PlotItem()
        self.setCentralItem(self.plot_item)
        
        # Lock aspect ratio to 1:1
        self.plot_item.setAspectLocked(True, ratio=1)
        
        self.img_item = pg.ImageItem()
        self.plot_item.addItem(self.img_item)
        # Replace tractor marker with an ArrowItem for proper rotation.
        self.tractor_marker = pg.ArrowItem(angle=0, tipAngle=45, baseAngle=25, headLen=40, tailLen=0, tailWidth=0, brush='g')
        self.plot_item.addItem(self.tractor_marker)
        self.plot_item.setAspectLocked(True)
        lut = np.empty((256, 4), dtype=np.uint8)
        for i in range(256):
            ratio = i / 255.0
            if ratio <= 0.5:
                ratio2 = ratio / 0.5
                r = 255
                g = int(255 * ratio2)
                b = int(255 * ratio2)
            else:
                ratio2 = (ratio - 0.5) / 0.5
                r = int(255 - 255 * ratio2)
                g = int(255 - 255 * ratio2)
                b = 255
            lut[i] = (r, g, b, 255)
        self.img_item.setLookupTable(lut)
    
    def update_grid(self, grid_x, grid_y, survey_grid, target_grid):
        if survey_grid is None or target_grid is None:
            return
            
        diff = target_grid - survey_grid
        min_diff = np.nanmin(diff)
        max_diff = np.nanmax(diff)
        color_bar_diff = np.max([np.abs(min_diff), np.abs(max_diff)])
        
        # Set the image data (transpose for proper orientation)
        self.img_item.setImage(diff.T, levels=(-color_bar_diff, color_bar_diff))
        
        # Set the rectangle that the image should cover in grid coordinates
        x0 = grid_x[0, 0]
        y0 = grid_y[0, 0]
        x1 = grid_x[-1, -1]
        y1 = grid_y[-1, -1]
        rect = QtCore.QRectF(x0, y0, x1 - x0, y1 - y0)
        self.img_item.setRect(rect)
        
        self.plot_item.setAspectLocked(True, ratio=1)
    
    def update_tractor(self, x, y, heading=0):
        self.tractor_marker.setPos(x, y)
        self.tractor_marker.setRotation(heading+90)

class ElevationDiffColorBar(QWidget):
    def __init__(self, min_diff=-1, max_diff=1, parent=None):
        super().__init__(parent)
        self.min_diff = min_diff
        self.max_diff = max_diff
        self.color_bar_diff = np.max([np.abs(self.min_diff), np.abs(self.max_diff)])
        self.line_value = 0
        self.setMinimumWidth(50)
        self.setMaximumWidth(120)
    
    def setRange(self, min_diff, max_diff):
        self.min_diff = min_diff
        self.max_diff = max_diff
        self.color_bar_diff = np.max([np.abs(self.min_diff), np.abs(self.max_diff)])
        self.update()
    
    def setLineValue(self, value):
        self.line_value = value
    
    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        gradient = QLinearGradient(0, rect.bottom(), 0, rect.top())
        gradient.setColorAt(0.0, QColor(0, 0, 255))
        gradient.setColorAt(0.5, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(255, 0, 0))
        painter.fillRect(rect, gradient)
        painter.setPen(Qt.black)
        font = QFont()
        # Use relative size based on widget height
        font_size = max(10, int(rect.height() / 15))
        font.setPointSize(font_size)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignBottom | Qt.AlignHCenter, f"{(-self.color_bar_diff):.2f}")
        painter.drawText(rect, Qt.AlignTop | Qt.AlignHCenter, f"{self.color_bar_diff:.2f}")
        mid_val = 0
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignHCenter, f"{mid_val:.2f}")
        # Draw the horizontal line at the specified value
        if -self.color_bar_diff <= self.line_value <= self.color_bar_diff:
            line_y = rect.bottom() - (self.line_value + self.color_bar_diff) / (2*self.color_bar_diff) * rect.height()
            if np.isnan(line_y):
                line_y = 0
            painter.setPen(QPen(QColor(0, 255, 0), 8))
            painter.drawLine(rect.left(), int(line_y), rect.right(), int(line_y))
