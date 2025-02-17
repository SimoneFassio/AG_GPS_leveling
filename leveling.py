# leveling.py
import numpy as np

def compute_best_plane(points):
    if not points:
        return 0, 0, 0
    xs = np.array([p["x"] for p in points])
    ys = np.array([p["y"] for p in points])
    zs = np.array([p["alt"] for p in points])
    A = np.vstack([np.ones_like(xs), xs, ys]).T
    coeff, residuals, rank, s = np.linalg.lstsq(A, zs, rcond=None)
    a, b, c = coeff
    return a, b, c

def compute_target_grid(grid_x, grid_y, slope_x_cm_per_100m, slope_y_cm_per_100m, base_elevation):
    """
    Calcola la griglia delle elevazioni target a partire dai parametri di pendenza.
    grid_x e grid_y sono le coordinate della griglia.
    """
    slope_x = slope_x_cm_per_100m / 10000.0
    slope_y = slope_y_cm_per_100m / 10000.0
    return base_elevation + grid_x * slope_x + grid_y * slope_y
