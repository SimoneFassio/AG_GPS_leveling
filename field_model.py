# field_model.py
import math
import json
import numpy as np

class FieldModel:
    def __init__(self):
        self.points = []  # Lista di punti: ogni punto è un dict con lat, lon, alt, x, y
        self.ref_lat = None
        self.ref_lon = None
        self.R = 6371000  # Raggio della Terra in metri

    def add_point(self, gps_data):
        lat = gps_data.get("latitude")
        lon = gps_data.get("longitude")
        alt = gps_data.get("altitude")
        # Set reference point if not defined
        if self.ref_lat is None or self.ref_lon is None:
            self.ref_lat = lat
            self.ref_lon = lon
        x, y = self.latlon_to_xy(lat, lon)
        # Always append the new point
        self.points.append({
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "x": x,
            "y": y
        })

    
    def latlon_to_xy(self, lat, lon):
        # Conversione lat/lon -> coordinate locali (approssimazione equirettangolare)
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        ref_lat_rad = math.radians(self.ref_lat)
        ref_lon_rad = math.radians(self.ref_lon)
        x = self.R * (lon_rad - ref_lon_rad) * math.cos(ref_lat_rad)
        y = self.R * (lat_rad - ref_lat_rad)
        return x, y

    def get_bounds(self):
        if not self.points:
            return 0, 0, 0, 0
        xs = [p["x"] for p in self.points]
        ys = [p["y"] for p in self.points]
        return min(xs), max(xs), min(ys), max(ys)

    def get_interpolated_grid(self, resolution=1.0):
        from scipy.interpolate import griddata
        if not self.points:
            return None, None, None
        xs = np.array([p["x"] for p in self.points])
        ys = np.array([p["y"] for p in self.points])
        alts = np.array([p["alt"] for p in self.points])
        min_x, max_x, min_y, max_y = self.get_bounds()
        # Crea una griglia regolare con la risoluzione specificata
        num_x = int((max_x - min_x) / resolution) + 1
        num_y = int((max_y - min_y) / resolution) + 1
        grid_x, grid_y = np.mgrid[min_x:max_x:complex(0, num_x),
                                    min_y:max_y:complex(0, num_y)]
        grid_z = griddata((xs, ys), alts, (grid_x, grid_y), method='linear')
        return grid_x, grid_y, grid_z

    def save_to_file(self, filename):
        data = {
            "ref_lat": self.ref_lat,
            "ref_lon": self.ref_lon,
            "points": self.points
        }
        with open(filename, "w") as f:
            json.dump(data, f)

    def load_from_file(self, filename):
        with open(filename, "r") as f:
            data = json.load(f)
        self.ref_lat = data.get("ref_lat")
        self.ref_lon = data.get("ref_lon")
        self.points = data.get("points", [])
