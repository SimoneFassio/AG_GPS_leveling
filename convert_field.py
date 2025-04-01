import math
import json
import sys

# Earth radius in meters
R = 6371000

def latlon_to_xy(lat, lon, ref_lat, ref_lon):
    """Convert geographic (lat, lon) to local Cartesian (x, y) using a simple equirectangular approximation."""
    ref_lat_rad = math.radians(ref_lat)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    ref_lon_rad = math.radians(ref_lon)
    x = R * (lon_rad - ref_lon_rad) * math.cos(ref_lat_rad)
    y = R * (lat_rad - math.radians(ref_lat))
    return x, y

def convert_elevation_file(infilename, outfilename):
    points = []
    header_found = False
    header_columns = []

    with open(infilename, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines
            if not line:
                continue
            # Look for header line (contains "Latitude" and "Longitude")
            # You can check for the header line signature
            if not header_found and "Latitude" in line and "Longitude" in line and "Elevation" in line:
                header_found = True
                header_columns = [col.strip() for col in line.split(',')]
                continue
            # Once header is found, process subsequent lines that start with a digit
            if header_found:
                # Skip if the line does not look like a data line (e.g. comments)
                if not line[0].isdigit():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 3:
                    continue
                try:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    elev = float(parts[2])
                except ValueError:
                    continue
                points.append({
                    "lat": lat,
                    "lon": lon,
                    "alt": elev  # altitude is same as elevation in this file
                })

    if not points:
        print("No valid points found in file.")
        return

    # Use the first point as the reference
    ref_lat = points[0]["lat"]
    ref_lon = points[0]["lon"]
    ref_alt = points[0]["alt"]

    # Compute local coordinates for each point
    for point in points:
        lat = point["lat"]
        lon = point["lon"]
        elev = point["alt"]
        x, y = latlon_to_xy(lat, lon, ref_lat, ref_lon)
        z = elev - ref_alt  # z as difference from the reference altitude
        point["x"] = x
        point["y"] = y
        point["z"] = z

    # Prepare JSON structure similar to field_model.py
    data = {
        "ref_lat": ref_lat,
        "ref_lon": ref_lon,
        "ref_alt": ref_alt,
        "points": points
    }

    with open(outfilename, "w") as outfile:
        json.dump(data, outfile, indent=2, default=float)
    print(f"Conversion complete. JSON saved to {outfilename}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_field.py <input_Elevation.txt> <output_json_file>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    convert_elevation_file(input_file, output_file)