import numpy as np
from scipy.optimize import minimize_scalar

def compute_best_plane(points):
    """
    Computes the best plane that balances cut and fill volumes while minimizing dirt movement.
    This is a memory-efficient implementation that works well for large datasets.
    
    Parameters:
    points -- List of dictionaries with keys 'x', 'y', 'z'
    
    Returns:
    a, b, c -- Coefficients for plane equation z = a + b*x + c*y
    """
    if not points:
        return 0, 0, 0
    
    xs = np.array([p["x"] for p in points])
    ys = np.array([p["y"] for p in points])
    zs = np.array([p["z"] for p in points])
    
    # Step 1: Use least squares to get initial slope parameters (b and c)
    # We'll optimize the offset (a) in step 2
    A = np.vstack([xs, ys]).T
    # We're solving for b and c in: z = b*x + c*y + a
    slope_params, residuals, rank, s = np.linalg.lstsq(A, zs, rcond=None)
    b, c = slope_params
    
    # Step 2: Find optimal offset (a) that balances cut and fill
    # Calculate the residuals when using the computed slopes
    residuals = zs - (b * xs + c * ys)
    
    # Function to find the median elevation that balances cut and fill
    def cut_fill_diff(a):
        # Compute deviations from the plane with offset a
        deviations = residuals - a
        # Sum of positive deviations (cut volume)
        cut = np.sum(deviations[deviations > 0])
        # Sum of negative deviations (fill volume)
        fill = np.sum(-deviations[deviations < 0])
        # Return absolute difference between cut and fill
        return abs(cut - fill)
    
    # Find the offset that balances cut and fill
    result = minimize_scalar(cut_fill_diff)
    a = result.x
    
    return a, b, c

def compute_best_offset(points, plane_b, plane_c):
    """Calculate the optimal vertical offset for a plane with given slopes."""
    if not points:
        return 0
        
    xs = np.array([p["x"] for p in points])
    ys = np.array([p["y"] for p in points])
    zs = np.array([p["z"] for p in points])
    
    # Calculate residuals using the given slopes
    residuals = zs - (plane_b * xs + plane_c * ys)
    
    # Return the median residual - this balances cut and fill
    return np.median(residuals)
    
def compute_target_grid(grid_x, grid_y, plane_a, plane_b, plane_c):
    """
    Calculate target elevation grid based on plane parameters.
    """
    return plane_a + grid_x * plane_b + grid_y * plane_c