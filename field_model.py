# field_model.py
import math
import json
import numpy as np
from scipy.interpolate import griddata

class FieldModel:
    def __init__(self):
        self.points = []
        self.ref_lat = None     # Reference latitude
        self.ref_lon = None     # Reference longitude
        self.ref_alt = None    # Reference altitude
        self.R = 6371000        # Earth radius in meters
        self.plane_a = 0
        self.plane_b = 0
        self.plane_c = 0
        
        # grid storage for leveling phase
        self.leveling_mode = False
        self.grid_x = None
        self.grid_y = None
        self.grid_z = None
        self.grid_resolution = 1.0  # Default grid resolution in meters


    def add_point(self, gps_data):
        lat = gps_data.get("latitude")
        lon = gps_data.get("longitude")
        alt = gps_data.get("altitude")
        
        # Set reference point if not defined
        if self.ref_lat is None or self.ref_lon is None or self.ref_alt is None:
            self.ref_lat = lat
            self.ref_lon = lon
            self.ref_alt = alt
            
        x, y = self.latlon_to_xy(lat, lon)
        z = alt - self.ref_alt  # Calculate z as altitude difference
        self.points.append({
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "x": x,
            "y": y,
            "z": z
        })

    def latlon_to_xy(self, lat, lon):
        """Convert geographic coordinates to Cartesian coordinates"""
        if self.ref_lat is None or self.ref_lon is None:
            return 0.0, 0.0
            
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        ref_lat_rad = math.radians(self.ref_lat)
        ref_lon_rad = math.radians(self.ref_lon)
        
        x = self.R * (lon_rad - ref_lon_rad) * math.cos(ref_lat_rad)
        y = self.R * (lat_rad - ref_lat_rad)
        return x, y

    def save_to_file(self, filename):
        """Save all points to JSON file"""
        data = {
            "ref_lat": self.ref_lat,
            "ref_lon": self.ref_lon,
            "ref_alt": self.ref_alt,
            "points": self.points
        }
        with open(filename, "w") as f:
            json.dump(data, f, default=float)

    def load_from_file(self, filename):
        """Load points from JSON file"""
        with open(filename, "r") as f:
            data = json.load(f)
            
        self.points = data["points"]
        self.ref_lat = data["ref_lat"]
        self.ref_lon = data["ref_lon"]
        self.ref_alt = data["ref_alt"] 

    def get_bounds(self):
        """Get bounding box of all points"""
        all_x = [p["x"] for p in self.points]
        all_y = [p["y"] for p in self.points]
        return min(all_x), max(all_x), min(all_y), max(all_y)
    
    
    def generate_leveling_grid(self, resolution=1.0):
        """Generate a fixed grid for leveling phase using interpolation"""
        self.grid_resolution = resolution
        
        # Get bounds with some padding
        points = self.points
        if not points:
            return False
            
        xs = [p["x"] for p in points]
        ys = [p["y"] for p in points]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        padding = 5.0  # 5m padding
        min_x -= padding
        max_x += padding
        min_y -= padding
        max_y += padding
    
        # Create grid
        x_range = np.arange(min_x, max_x + resolution, resolution)
        y_range = np.arange(min_y, max_y + resolution, resolution)
        self.grid_x, self.grid_y = np.meshgrid(x_range, y_range)
        
        # Get survey points
        points_xy = np.array([(p["x"], p["y"]) for p in points])
        points_z = np.array([p["z"] for p in points])
        
        # Perform interpolation
        self.grid_z = griddata(points_xy, points_z, (self.grid_x, self.grid_y), method='linear')
        
        # Set leveling mode flag
        self.leveling_mode = True
        
        return True
    
    def update_grid_elevation(self, current_lat, current_lon, current_elev, radius, direction_deg):
        """Update grid points along a line that is perpendicular to the given heading,
        centered at (x0, y0). 'radius' defines the total length of the line.
        Only grid cells within a bounding box (derived from the line parameters)
        are evaluated, to reduce computation.
        """
        if not self.leveling_mode or self.grid_z is None:
            return

        # Convert current position to XY
        x0, y0 = self.latlon_to_xy(current_lat, current_lon)

        # Convert navigation heading to a unit vector.
        # Navigation: 0° is North, 90° is East.
        direction_rad = math.radians(direction_deg)
        dx_dir = math.sin(direction_rad)
        dy_dir = math.cos(direction_rad)
        mag = math.sqrt(dx_dir**2 + dy_dir**2)
        if mag > 0:
            dx_dir /= mag
            dy_dir /= mag

        # Get the line perpendicular to the heading (rotate 90° counterclockwise)
        line_axis_x = -dy_dir
        line_axis_y = dx_dir

        # Line parameters
        line_width = 0.5            # Maximum perpendicular distance from the line (in meters)
        half_length = radius / 2.0    # Half the total length of the line

        # Determine a bounding box that fully encloses the line area (line segment + tolerance)
        # The extreme points of the line segment:
        x1 = x0 + half_length * line_axis_x
        y1 = y0 + half_length * line_axis_y
        x2 = x0 - half_length * line_axis_x
        y2 = y0 - half_length * line_axis_y
        # Bounding box limits with extra margin of line_width
        min_bound_x = min(x0, x1, x2) - line_width
        max_bound_x = max(x0, x1, x2) + line_width
        min_bound_y = min(y0, y1, y2) - line_width
        max_bound_y = max(y0, y1, y2) + line_width

        # Use the sorted 1D arrays from grid creation.
        # Assuming self.grid_x[0, :] contains sorted x values
        # and self.grid_y[:, 0] contains sorted y values.
        x_range = self.grid_x[0, :]
        y_range = self.grid_y[:, 0]

        # Find index bounds using np.searchsorted
        j_min = np.searchsorted(x_range, min_bound_x, side='left')
        j_max = np.searchsorted(x_range, max_bound_x, side='right')
        i_min = np.searchsorted(y_range, min_bound_y, side='left')
        i_max = np.searchsorted(y_range, max_bound_y, side='right')

        grid_shape = self.grid_x.shape
        modified = False

        # Loop only over the selected indices
        for i in range(i_min, min(i_max, grid_shape[0])):
            for j in range(j_min, min(j_max, grid_shape[1])):
                # Skip grid cells with no interpolated value
                if np.isnan(self.grid_z[i, j]):
                    continue

                x = self.grid_x[i, j]
                y = self.grid_y[i, j]
                dx = x - x0
                dy = y - y0

                # Project (dx, dy) onto the line_axis (perpendicular to heading)
                proj = dx * line_axis_x + dy * line_axis_y

                # Only consider points within half-length of the line segment
                if abs(proj) > half_length:
                    continue

                # Compute perpendicular distance from the grid point to the line
                perp = abs(dx * line_axis_y - dy * line_axis_x)
                if perp <= line_width:
                    self.grid_z[i, j] = current_elev
                    modified = True

        return modified
    
    def get_grid_as_points(self):
        """Convert current grid to a list of points for saving"""
        if not self.leveling_mode:
            return self.points
            
        points = []
        grid_shape = self.grid_x.shape
        
        for i in range(grid_shape[0]):
            for j in range(grid_shape[1]):
                # Skip NaN values in the grid
                if np.isnan(self.grid_z[i, j]):
                    continue
                    
                x = self.grid_x[i, j]
                y = self.grid_y[i, j]
                z = self.grid_z[i, j]
                
                # Convert back to lat, lon
                lat, lon = self.xy_to_latlon(x, y)
                alt = z + self.ref_alt
                
                points.append({
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                    "x": x,
                    "y": y,
                    "z": z
                })
        
        return points
    
    def save_grid_as_points(self, filename):
        """Save current grid as points to a file"""
        points = self.get_grid_as_points()
        data = {
            "ref_lat": self.ref_lat,
            "ref_lon": self.ref_lon,
            "ref_alt": self.ref_alt,
            "points": points
        }
        with open(filename, "w") as f:
            json.dump(data, f, default=float)
    
    def xy_to_latlon(self, x, y):
        """Convert Cartesian coordinates back to geographic coordinates"""
        if self.ref_lat is None or self.ref_lon is None:
            return 0.0, 0.0
            
        ref_lat_rad = math.radians(self.ref_lat)
        ref_lon_rad = math.radians(self.ref_lon)
        
        lat_rad = y / self.R + ref_lat_rad
        lon_rad = x / (self.R * math.cos(ref_lat_rad)) + ref_lon_rad
        
        return math.degrees(lat_rad), math.degrees(lon_rad)

    def update_points_from_grid(self):
        """Update points with the current grid values"""
        if not self.leveling_mode:
            return
        
        points = self.get_grid_as_points()
        self.points = points