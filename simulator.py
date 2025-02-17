import socket
import struct
import time
import random

class GPSSimulator:
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

    def update_position(self):
        # Simulate movement in a square pattern
        if self.heading < 90:
            self.latitude += 0.00001
            self.longitude += 0.00001
        elif self.heading < 180:
            self.latitude -= 0.00001
            self.longitude += 0.00001
        elif self.heading < 270:
            self.latitude -= 0.00001
            self.longitude -= 0.00001
        else:
            self.latitude += 0.00001
            self.longitude -= 0.00001

        self.heading = (self.heading + 1) % 360
        self.altitude += random.uniform(-0.1, 0.1)
        self.roll = random.uniform(-5, 5)
        self.imu_heading = self.heading
        self.imu_roll = self.roll
        self.imu_pitch = random.uniform(-2, 2)
        self.imu_yaw_rate = random.uniform(-1, 1)

    def run(self):
        print("Starting GPS Simulator...")
        try:
            while True:
                self.update_position()
                nmea_pgn = self.generate_nmea_pgn()
                self.sock.sendto(nmea_pgn, self.destination)
                time.sleep(0.1)  # Send data every 100ms
        except KeyboardInterrupt:
            print("\nStopping GPS Simulator...")

if __name__ == "__main__":
    simulator = GPSSimulator()
    simulator.run()