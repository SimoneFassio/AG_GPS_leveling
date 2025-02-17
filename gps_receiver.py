# gps_receiver.py
import socket, struct
from PyQt5.QtCore import QThread, pyqtSignal

def parse_gps_data(data):
    """
    Parse del pacchetto GPS a 57 byte.
    Ritorna un dizionario con i valori parsati oppure None in caso di errore.
    """
    if len(data) != 57:
        return None
    header = data[:5]
    if header[0] != 0x80 or header[1] != 0x81 or header[2] != 0x7C or header[3] != 0xD6 or header[4] != 0x33:
        return None
    checksum = sum(data[2:56]) & 0xFF
    if checksum != data[56]:
        return None
    fmt = "<ddfffffHBHHHhhh"  # < = little-endian
    unpacked = struct.unpack(fmt, data[5:56])
    gps_data = {
        "longitude":       unpacked[0],
        "latitude":        unpacked[1],
        "headingTrueDual": unpacked[2],
        "headingTrue":     unpacked[3],
        "speed":           unpacked[4],
        "roll":            unpacked[5],
        "altitude":        unpacked[6],
        "satellitesTracked": unpacked[7],
        "fixQuality":      unpacked[8],
        "hdopX100":        unpacked[9],
        "ageX100":         unpacked[10],
        "imuHeading":      unpacked[11],
        "imuRoll":         unpacked[12],
        "imuPitch":        unpacked[13],
        "imuYawRate":      unpacked[14],
    }
    return gps_data

class GPSReceiver(QThread):
    new_data = pyqtSignal(dict)
    
    def __init__(self, port=15555, parent=None):
        super().__init__(parent)
        self.port = port
        self.running = True

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1', self.port))
        sock.settimeout(1.0)
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                parsed = parse_gps_data(data)
                if parsed:
                    self.new_data.emit(parsed)
            except socket.timeout:
                continue
            except Exception as e:
                print("GPSReceiver error:", e)
        sock.close()
    
    def stop(self):
        self.running = False
        self.wait()
