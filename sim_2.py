import socket
import struct
import time
import math
import threading
from pynput import keyboard

class KeyboardGPSSimulator:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.destination = ("127.0.0.1", 15555)
        self.latitude = 45.0  # Starting latitude
        self.longitude = 9.0  # Starting longitude
        self.altitude = 100.0  # Starting altitude
        self.speed = 5.0  # Speed in km/h
        self.heading = 0.0  # Heading in degrees
        self.roll = 0.0  # Roll in degrees
        self.satellites = 12  # Number of satellites tracked
        self.fix_quality = 1  # Fix quality
        self.hdop = 0.8  # Horizontal dilution of precision
        self.age = 0.1  # Age of correction data
        self.imu_heading = 0.0  # IMU heading
        self.imu_roll = 0.0  # IMU roll
        self.imu_pitch = 0.0  # IMU pitch
        self.imu_yaw_rate = 0.0  # IMU yaw rate
        
        # Movement control
        self.keys_pressed = set()
        self.step_size = 0.000005  # Movement increment per step
        self.altitude_step = 0.01  # Altitude change per step
        
        # Last position to calculate heading
        self.last_lat = self.latitude
        self.last_lon = self.longitude
        
        # Flag to control the main loop
        self.running = True
    
    def generate_nmea_pgn(self):
        nmea_pgn = bytearray(57)
        nmea_pgn[0] = 0x80
        nmea_pgn[1] = 0x81
        nmea_pgn[2] = 0x7C
        nmea_pgn[3] = 0xD6
        nmea_pgn[4] = 51  # Total array count minus 6

        # Longitude
        nmea_pgn[5:13] = struct.pack('<d', self.longitude)
        # Latitude
        nmea_pgn[13:21] = struct.pack('<d', self.latitude)
        # Dual antenna heading
        nmea_pgn[21:25] = struct.pack('<f', self.heading)
        # Single antenna heading
        nmea_pgn[25:29] = struct.pack('<f', self.heading)
        # Speed (km/h)
        nmea_pgn[29:33] = struct.pack('<f', self.speed)
        # Roll
        nmea_pgn[33:37] = struct.pack('<f', self.roll)
        # Altitude
        nmea_pgn[37:41] = struct.pack('<f', self.altitude)
        # Satellites tracked
        nmea_pgn[41:43] = struct.pack('<H', self.satellites)
        # Fix quality
        nmea_pgn[43] = self.fix_quality
        # HDOP
        nmea_pgn[44:46] = struct.pack('<H', int(self.hdop * 100))
        # Age of correction data
        nmea_pgn[46:48] = struct.pack('<H', int(self.age * 100))
        # IMU heading
        nmea_pgn[48:50] = struct.pack('<H', int(self.imu_heading))
        # IMU roll
        nmea_pgn[50:52] = struct.pack('<h', int(self.imu_roll))
        # IMU pitch
        nmea_pgn[52:54] = struct.pack('<h', int(self.imu_pitch))
        # IMU yaw rate
        nmea_pgn[54:56] = struct.pack('<h', int(self.imu_yaw_rate))

        # Calculate checksum
        ck_a = sum(nmea_pgn[2:56]) & 0xFF
        nmea_pgn[56] = ck_a

        return nmea_pgn

    def on_key_press(self, key):
        try:
            # Convert to string to handle both Key objects and characters
            key_char = key.char.lower() if hasattr(key, 'char') else str(key)
            self.keys_pressed.add(key_char)
        except AttributeError:
            # Special keys
            if key == keyboard.Key.plus or key == keyboard.Key.add:
                self.keys_pressed.add('+')
            elif key == keyboard.Key.minus or key == keyboard.Key.subtract:
                self.keys_pressed.add('-')
            elif key == keyboard.Key.esc:
                self.running = False
                return False  # Stop listener

    def on_key_release(self, key):
        try:
            key_char = key.char.lower() if hasattr(key, 'char') else str(key)
            self.keys_pressed.discard(key_char)
        except AttributeError:
            if key == keyboard.Key.plus or key == keyboard.Key.add:
                self.keys_pressed.discard('+')
            elif key == keyboard.Key.minus or key == keyboard.Key.subtract:
                self.keys_pressed.discard('-')

    def update_position(self):
        # Save current position for heading calculation
        self.last_lat = self.latitude
        self.last_lon = self.longitude
        
        # Handle WASD for lat/lon movement
        if 'w' in self.keys_pressed:  # North
            self.latitude += self.step_size
        if 's' in self.keys_pressed:  # South
            self.latitude -= self.step_size
        if 'd' in self.keys_pressed:  # East
            self.longitude += self.step_size
        if 'a' in self.keys_pressed:  # West
            self.longitude -= self.step_size
        
        # Handle +/- for altitude
        if '+' in self.keys_pressed:
            self.altitude += self.altitude_step
        if '-' in self.keys_pressed:
            self.altitude -= self.altitude_step

        # Calculate heading based on movement direction
        delta_lat = self.latitude - self.last_lat
        delta_lon = self.longitude - self.last_lon
        
        if delta_lat != 0 or delta_lon != 0:
            # Calculate heading in degrees (0° = North, 90° = East)
            heading_rad = math.atan2(delta_lon, delta_lat)
            self.heading = (math.degrees(heading_rad) + 360) % 360
            self.imu_heading = self.heading
        
        # Update related values
        self.roll = 0  # Simplified for keyboard control
        self.imu_roll = self.roll
        self.imu_pitch = 0
        self.imu_yaw_rate = 0
        
        # Calculate rough speed based on movement (in km/h)
        dist = math.sqrt(delta_lat**2 + delta_lon**2) * 111000  # Rough distance in meters
        self.speed = dist * 36000  # Convert to km/h (assuming 0.1s update interval)

    def run(self):
        print("Starting Keyboard GPS Simulator...")
        print("Controls:")
        print("  W/A/S/D - Control latitude/longitude")
        print("  +/- - Control altitude")
        print("  ESC - Quit")
        
        # Start keyboard listener in a separate thread
        listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        listener.start()
        
        try:
            while self.running:
                self.update_position()
                nmea_pgn = self.generate_nmea_pgn()
                self.sock.sendto(nmea_pgn, self.destination)
                
                # Print current status
                print(f"\rLat: {self.latitude:.6f} Lon: {self.longitude:.6f} Alt: {self.altitude:.1f} " +
                      f"Heading: {self.heading:.1f}°", end="")
                
                time.sleep(0.1)  # Update every 100ms
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            print("\nStopping GPS Simulator...")
            listener.stop()

if __name__ == "__main__":
    simulator = KeyboardGPSSimulator()
    simulator.run()