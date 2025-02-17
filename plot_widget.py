# plot_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg
import numpy as np
from PyQt5.QtGui import QPainter, QLinearGradient, QColor, QFont
from PyQt5.QtCore import Qt

class FieldPlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.plot_widget = pg.PlotWidget(title="Field Survey")
        layout.addWidget(self.plot_widget)
        self.scatter = pg.ScatterPlotItem()
        self.plot_widget.addItem(self.scatter)
        # Marker per la posizione attuale del trattore
        self.tractor_marker = pg.ScatterPlotItem(pen=pg.mkPen(None), brush=pg.mkBrush('y'), size=10)
        self.plot_widget.addItem(self.tractor_marker)
    
    def update_points(self, points):
        if not points:
            return
        xs = np.array([p["x"] for p in points])
        ys = np.array([p["y"] for p in points])
        alts = np.array([p["alt"] for p in points])
        norm = (alts - np.min(alts)) / (np.ptp(alts) + 1e-6)
        colors = [pg.intColor(int(255 * val), 255, maxValue=255) for val in norm]
        spots = [{'pos': (x, y), 'data': 1, 'brush': color} for x, y, color in zip(xs, ys, colors)]
        self.scatter.setData(spots)
    
    def update_tractor(self, x, y):
        self.tractor_marker.setData([{'pos': (x, y)}])

class LevelingPlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.plot_widget = pg.PlotWidget(title="Levelling Phase")
        layout.addWidget(self.plot_widget)
        self.img_item = pg.ImageItem()
        self.plot_widget.addItem(self.img_item)
        self.tractor_marker = pg.ScatterPlotItem(pen=pg.mkPen(None), brush=pg.mkBrush('y'), size=10)
        self.plot_widget.addItem(self.tractor_marker)
        self.plot_widget.setAspectLocked(True)
        # Try to load the RdBu colormap, otherwise create a fallback lookup table
        try:
            from pyqtgraph import colormap
            cmap = colormap.get('RdBu')
            lut = cmap.getLookupTable(0.0, 1.0, 256)
        except Exception as e:
            print("RdBu colormap not found, using fallback. Error:", e)
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
      self.img_item.setImage(diff.T, levels=(min_diff, max_diff))
      # Imposta il rettangolo che l'immagine deve coprire in coordinate della griglia
      from pyqtgraph.Qt import QtCore
      x0 = grid_x[0, 0]
      y0 = grid_y[0, 0]
      x1 = grid_x[-1, -1]
      y1 = grid_y[-1, -1]
      rect = QtCore.QRectF(x0, y0, x1 - x0, y1 - y0)
      self.img_item.setRect(rect)

    
    def update_tractor(self, x, y):
        self.tractor_marker.setData([{'pos': (x, y)}])

class ElevationDiffColorBar(QWidget):
    def __init__(self, min_diff=-1, max_diff=1, parent=None):
        super().__init__(parent)
        self.min_diff = min_diff
        self.max_diff = max_diff
        self.setMinimumWidth(50)
        self.setMaximumWidth(50)
    
    def setRange(self, min_diff, max_diff):
        self.min_diff = min_diff
        self.max_diff = max_diff
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        gradient = QLinearGradient(0, rect.bottom(), 0, rect.top())
        gradient.setColorAt(0.0, QColor(255, 0, 0))
        gradient.setColorAt(0.5, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(0, 0, 255))
        painter.fillRect(rect, gradient)
        painter.setPen(Qt.black)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignBottom | Qt.AlignHCenter, f"{self.min_diff:.2f}")
        painter.drawText(rect, Qt.AlignTop | Qt.AlignHCenter, f"{self.max_diff:.2f}")
        mid_val = (self.min_diff + self.max_diff) / 2.0
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignHCenter, f"{mid_val:.2f}")
