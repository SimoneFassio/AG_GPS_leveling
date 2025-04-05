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
        self.rotation_angle = 0.0  # new field for storing rotation in radians
        self.vertical_offset = 0.0 # Vertical offset for leveling
        self.vertical_offset_old = 0.0 # Old vertical offset for leveling


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
        """Save all points and field properties to JSON file"""
        data = {
            "ref_lat": self.ref_lat,
            "ref_lon": self.ref_lon,
            "ref_alt": self.ref_alt,
            "rotation_angle": self.rotation_angle,  # Save the rotation angle
            "points": self.points
        }
        with open(filename, "w") as f:
            json.dump(data, f, default=float)

    def load_from_file(self, filename):
        """Load points and field properties from JSON file"""
        with open(filename, "r") as f:
            data = json.load(f)
            
        self.points = data["points"]
        self.ref_lat = data["ref_lat"]
        self.ref_lon = data["ref_lon"]
        self.ref_alt = data["ref_alt"]
        
        # Load the rotation angle if it exists, default to 0.0
        self.rotation_angle = data.get("rotation_angle", 0.0)
        
        # If the field had a non-zero rotation, apply it to points immediately
        if abs(self.rotation_angle) > 1e-9:
            print(f"Applying saved rotation angle of {math.degrees(self.rotation_angle):.2f}°")
            # Points are already rotated in the file, no need to rotate again
        
        return True

    def get_bounds(self):
        """Get bounding box of all points"""
        all_x = [p["x"] for p in self.points]
        all_y = [p["y"] for p in self.points]
        return min(all_x), max(all_x), min(all_y), max(all_y)
    
    
    def generate_leveling_grid(self, resolution=1.0):
        """
        Generate a grid for leveling that follows the concave shape of the field points.
        Ignores large holes in the interior (>5m across) where no survey data was collected.
        """
        from scipy.spatial import Delaunay, ConvexHull
        from shapely.geometry import Polygon, Point
        from shapely.ops import unary_union
        
        points = self.points
        if not points:
            return False

        # 1) Find min altitude among all points and update reference
        min_alt_in_points = min(p["alt"] for p in points)
        self.ref_alt = min_alt_in_points
        for p in points:
            p["z"] = p["alt"] - self.ref_alt

        # 2) Extract x,y coordinates
        self.grid_resolution = resolution
        xs = np.array([p["x"] for p in points])
        ys = np.array([p["y"] for p in points])
        points_xy = np.column_stack((xs, ys))

        # Quick fallback if too few points
        if len(points_xy) < 3:
            return False

        # 3) Build concave hull via Delaunay -> alpha-like filtering. Fallback to convex hull on error.
        try:
            tri = Delaunay(points_xy)
            triangles = points_xy[tri.simplices]
            # Compute max edge length of each triangle
            edge_lengths = []
            for t in triangles:
                e1 = np.linalg.norm(t[1] - t[0])
                e2 = np.linalg.norm(t[2] - t[1])
                e3 = np.linalg.norm(t[0] - t[2])
                edge_lengths.append(max(e1, e2, e3))
            # Filter out "large" triangles
            alpha = np.percentile(edge_lengths, 90)
            valid_triangles = [Polygon(t) for t, ln in zip(triangles, edge_lengths) if ln < alpha]

            if not valid_triangles:
                hull = ConvexHull(points_xy)
                field_boundary = Polygon(points_xy[hull.vertices])
            else:
                polygons = unary_union(valid_triangles)
                # If union is multi-polygon, keep the largest
                if polygons.geom_type == 'MultiPolygon':
                    field_boundary = max(polygons.geoms, key=lambda p: p.area)
                else:
                    field_boundary = polygons
        except:
            hull = ConvexHull(points_xy)
            field_boundary = Polygon(points_xy[hull.vertices])

        # 4) Remove large holes. Any interior ring with area > ~25 m² (≈ circle of diameter 5 m)
        cleaned_interior_polygons = []
        for interior in field_boundary.interiors:
            hole_poly = Polygon(interior)
            # If hole is smaller than 25 m², keep it. Otherwise skip it.
            if hole_poly.area < 25:
                cleaned_interior_polygons.append(hole_poly)

        # Rebuild polygon without large holes
        field_boundary = Polygon(field_boundary.exterior.coords, [p.exterior.coords for p in cleaned_interior_polygons])

        # 5) Create a 5 m buffer inside the boundary for partial regions
        #    (means we do NOT fill grid for regions more than 5 m away from survey boundaries).
        actual_field = field_boundary.buffer(5.0)

        # If buffering inward removes everything, just skip
        if actual_field.is_empty:
            return False

        # 6) Enclose the boundary for final bounding box
        min_x, min_y, max_x, max_y = actual_field.bounds
        x_range = np.arange(min_x, max_x + resolution, resolution)
        y_range = np.arange(min_y, max_y + resolution, resolution)
        self.grid_x, self.grid_y = np.meshgrid(x_range, y_range)
        grid_shape = self.grid_x.shape

        # 7) Initialize grid_z with NaN
        self.grid_z = np.full(grid_shape, np.nan)

        # 8) Prepare interpolation
        points_z = np.array([p["z"] for p in points])

        # 9) Assign z-values only inside actual_field polygon
        inside_points = []
        inside_indices = []
        for i in range(grid_shape[0]):
            for j in range(grid_shape[1]):
                x = self.grid_x[i, j]
                y = self.grid_y[i, j]
                if actual_field.contains(Point(x, y)):
                    inside_points.append((x, y))
                    inside_indices.append((i, j))

        # Interpolate wherever inside_points exist
        if inside_points:
            inside_points = np.array(inside_points)
            z_values = griddata(points_xy, points_z, inside_points, method='linear')
            for k, (i, j) in enumerate(inside_indices):
                self.grid_z[i, j] = z_values[k]

        self.leveling_mode = True
        return True
    
    def update_grid_elevation(self, x0, y0, current_elev, radius, direction_deg):
        """Update grid points along a line that is perpendicular to the given heading,
        centered at (x0, y0). 'radius' defines the total length of the line.
        Only grid cells within a bounding box (derived from the line parameters)
        are evaluated, to reduce computation.
        """
        if not self.leveling_mode or self.grid_z is None:
            return

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
    
    def apply_vertical_offset_grid(self, offset):
        """
        Apply a vertical offset to all z values in the grid.
        
        Args:
            offset: Vertical offset in meters to apply.
            
        Returns:
            bool: True if applied successfully, False if no grid or not in leveling mode.
        """
        if not self.leveling_mode or self.grid_z is None:
            return False
            
        # Add offset to all non-NaN values in the grid
        valid_mask = ~np.isnan(self.grid_z)
        if np.any(valid_mask):
            self.grid_z[valid_mask] += offset
            return True
        
        return False
    
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
            "rotation_angle": self.rotation_angle,  # Save rotation angle
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
        # if not self.leveling_mode:
        #     return
        
        points = self.get_grid_as_points()
        self.points = points

    def rotate_field(self, angle_radians):
        """Rotate all points in-place by angle_radians around origin."""
        cos_a = math.cos(angle_radians)
        sin_a = math.sin(angle_radians)
        for p in self.points:
            x_old, y_old = p["x"], p["y"]
            x_new = x_old * cos_a - y_old * sin_a
            y_new = x_old * sin_a + y_old * cos_a
            p["x"] = x_new
            p["y"] = y_new

    def import_from_elevation_txt_to_grid(self, filename, resolution=1.0):
        """Import data from Elevation.txt directly to a grid structure for efficiency"""
        # First, parse the Elevation.txt file into temporary points
        temp_points = []
        header_found = False
        ref_lat = None
        ref_lon = None
        
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines
                if not line:
                    continue
                
                # Look for the header line with column names
                if not header_found and "Latitude,Longitude,Elevation" in line:
                    header_found = True
                    continue
                
                # Extract StartFix for reference if we find it 
                if not header_found and line.startswith("StartFix"):
                    parts = line.strip().split(",")
                    if len(parts) >= 2:
                        try:
                            ref_lat = float(parts[0])
                            ref_lon = float(parts[1]) 
                        except ValueError:
                            pass
                    continue
                
                # Once header is found, process data lines
                if header_found and line[0].isdigit():
                    parts = line.split(",")
                    if len(parts) < 3:
                        continue
                    
                    try:
                        lat = float(parts[0])
                        lon = float(parts[1])
                        elev = float(parts[2])
                        
                        # Set reference point to first point if not defined
                        if ref_lat is None or ref_lon is None:
                            ref_lat = lat
                            ref_lon = lon
                        
                        temp_points.append({"lat": lat, "lon": lon, "alt": elev})
                    except ValueError:
                        continue
        
        if not temp_points:
            return False
        
        # Set reference coordinates from the first valid point
        self.ref_lat = ref_lat if ref_lat is not None else temp_points[0]["lat"]
        self.ref_lon = ref_lon if ref_lon is not None else temp_points[0]["lon"]
        
        # Find minimum altitude to use as reference
        min_alt = min(p["alt"] for p in temp_points)
        self.ref_alt = min_alt
        
        # Convert the points to local XY coordinates
        for p in temp_points:
            x, y = self.latlon_to_xy(p["lat"], p["lon"])
            p["x"] = x
            p["y"] = y
            p["z"] = p["alt"] - self.ref_alt
        
        # Now directly generate a grid from these points
        xs = [p["x"] for p in temp_points]
        ys = [p["y"] for p in temp_points]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        padding = 5.0  # 5m padding
        min_x -= padding
        max_x += padding
        min_y -= padding
        max_y += padding

        x_range = np.arange(min_x, max_x + resolution, resolution)
        y_range = np.arange(min_y, max_y + resolution, resolution)
        self.grid_x, self.grid_y = np.meshgrid(x_range, y_range)
        
        # Interpolate Z
        points_xy = np.array([(p["x"], p["y"]) for p in temp_points])
        points_z = np.array([p["z"] for p in temp_points])
        self.grid_z = griddata(points_xy, points_z, (self.grid_x, self.grid_y), method='linear')
        
        self.leveling_mode = True
        self.rotation_angle = 0.0  # Initialize rotation angle
        
        # Success
        return True