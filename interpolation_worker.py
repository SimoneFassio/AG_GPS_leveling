# interpolation_worker.py
from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np
from scipy.interpolate import griddata

class InterpolationWorker(QThread):
    result_ready = pyqtSignal(object, object, object)  # grid_x, grid_y, survey_grid

    def __init__(self, points, resolution=1.0, parent=None):
        super().__init__(parent)
        self.points = points
        self.resolution = resolution

    def run(self):
        if not self.points:
            self.result_ready.emit(None, None, None)
            return
        xs = np.array([p["x"] for p in self.points])
        ys = np.array([p["y"] for p in self.points])
        alts = np.array([p["alt"] for p in self.points])
        min_x, max_x = xs.min(), xs.max()
        min_y, max_y = ys.min(), ys.max()
        num_x = int((max_x - min_x) / self.resolution) + 1
        num_y = int((max_y - min_y) / self.resolution) + 1
        grid_x, grid_y = np.mgrid[min_x:max_x:complex(0, num_x),
                                    min_y:max_y:complex(0, num_y)]
        # Use 'nearest' interpolation if not enough points for linear interpolation
        if len(self.points) < 4:
            survey_grid = griddata((xs, ys), alts, (grid_x, grid_y), method='nearest')
        else:
            survey_grid = griddata((xs, ys), alts, (grid_x, grid_y), method='linear')
        self.result_ready.emit(grid_x, grid_y, survey_grid)
