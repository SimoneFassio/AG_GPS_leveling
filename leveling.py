import numpy as np
from scipy.optimize import minimize
from scipy.optimize import minimize_scalar

def get_initial_plane_params(points):
    """Calculate initial plane parameters using least squares"""
    if not points:
        return 0, 0, 0
    
    xs = np.array([p["x"] for p in points])
    ys = np.array([p["y"] for p in points])
    zs = np.array([p["z"] for p in points])
    
    # Step 1: Use least squares to get initial slope parameters (b and c)
    A = np.vstack([np.ones_like(xs), xs, ys]).T
    params, residuals, rank, s = np.linalg.lstsq(A, zs, rcond=None)
    a, b, c = params
    
    return a, b, c

def compute_best_plane(points):
    """Directly optimize all plane parameters to minimize dirt movement"""
    xs = np.array([p["x"] for p in points])
    ys = np.array([p["y"] for p in points])
    zs = np.array([p["z"] for p in points])
    
    def total_movement(params):
        a, b, c = params
        deviations = zs - (a + b * xs + c * ys)
        cut = np.sum(deviations[deviations > 0])
        fill = np.sum(-deviations[deviations < 0])
        # We want to minimize total movement (cut+fill) while keeping them balanced
        balance_penalty = abs(cut - fill) * 0.5
        return cut + fill + balance_penalty
    
    # Get initial guess using least squares method
    initial_guess = get_initial_plane_params(points)
    
    # Print information for debugging
    print(f"Initial guess: a={initial_guess[0]:.4f}, b={initial_guess[1]:.4f}, c={initial_guess[2]:.4f}")
    
    # Perform optimization
    result = minimize(total_movement, initial_guess, method='Nelder-Mead')
    
    # Print optimization results
    print(f"Optimization success: {result.success}")
    print(f"Optimized plane: a={result.x[0]:.4f}, b={result.x[1]:.4f}, c={result.x[2]:.4f}")
    
    # Calculate and print cut/fill volumes for validation
    final_deviations = zs - (result.x[0] + result.x[1] * xs + result.x[2] * ys)
    cut = np.sum(final_deviations[final_deviations > 0])
    fill = np.sum(-final_deviations[final_deviations < 0])
    print(f"Cut volume: {cut:.2f}, Fill volume: {fill:.2f}, Difference: {abs(cut-fill):.2f}")
    
    return result.x

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