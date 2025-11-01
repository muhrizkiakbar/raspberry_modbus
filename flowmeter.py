from sys import set_coroutine_origin_tracking_depth
import crcmod
import time
import struct
import minimalmodbus
import threading


class Flowmeter:
    def __init__(self, ser_ports, config):
        self.config = config
        self.ser_ports = ser_ports
        self.instruments = {}
        self.last_key = ""
        self.current_debit = 0
        self.current_water_height = 0
        self.current_velocity = 0
        self.current_time = 0
        self.lock = threading.Lock()

        for device in config["devices"]:
            if (
                "rs_rad" in device["name"].lower()
                and "direct_rs485" in device["type"].lower()
            ):
                print("======================================")
                print(device["type"])
                print(device["name"])
                print("======================================")
                port = device["port"]
                slave_addr = 1
                key = f"{port}"
                instr = minimalmodbus.Instrument(port, slave_addr)
                instr.serial.baudrate = ser_ports[port].baudrate
                instr.serial.bytesize = ser_ports[port].bytesize
                instr.serial.parity = ser_ports[port].parity
                instr.serial.stopbits = ser_ports[port].stopbits
                instr.serial.timeout = 1
                instr.mode = minimalmodbus.MODE_RTU
                self.last_key = key
                self.instruments[key] = instr

                print("======================================")
                print(self.instruments)
                print("======================================")
                self.set_section_config(instr, device["section_parameters"])

                break

    def read_sensor_data(self, sensor, port):
        """Baca semua data sensor"""
        instr = self.instruments[self.last_key]

        with self.lock:  # 🔒 hanya 1 thread yang bisa akses saat ini
            current_time = time.time()
            elapsed = current_time - self.current_time

            # Cek apakah sudah lewat 1 menit sejak update terakhir
            if elapsed < 60:
                # Belum lewat 1 menit, kembalikan nilai terakhir saja
                if sensor["name"] == "water_height":
                    return self.current_water_height
                elif sensor["name"] == "velocity":
                    return self.current_velocity
                elif sensor["name"] == "debit":
                    return self.current_debit

            # Jika sudah lewat 1 menit → baca ulang
            try:
                if sensor["name"] == "water_height":
                    depth_info = instr.read_register(1003, 0, functioncode=3)
                    if depth_info:
                        value = depth_info / 1000.0
                        self.current_water_height = value
                        self.current_time = current_time
                        return value

                elif sensor["name"] == "velocity":
                    velocity_cms = instr.read_register(1004, 0, functioncode=3)
                    value = velocity_cms
                    self.current_velocity = value
                    self.current_time = current_time
                    return value

                elif sensor["name"] == "debit":
                    flow_raw = instr.read_register(1002, 0, functioncode=3)
                    value = flow_raw / 1000.0
                    self.current_debit = value
                    self.current_time = current_time
                    return value

    def set_section_config(self, instr, section_parameters):
        """Konfigurasi penampang trapezoid sesuai data Anda"""
        try:
            print("=========================instr")
            print(instr)
            print("=========================instr")

            # Section type: 1=Trapezoid
            instr.write_register(
                1042, section_parameters["section_type"], functioncode=6
            )

            # Section parameters untuk trapezoid
            # Size1 = tinggi saluran = 2800 mm
            # instrument.write_register(1043, 2500, functioncode=6)
            instr.write_register(1043, section_parameters["size1"], functioncode=6)

            # Size2 = lebar slope = 1000 mm
            # instrument.write_register(1044, 1000, functioncode=6)
            instr.write_register(1044, section_parameters["size2"], functioncode=6)

            # Size3 = lebar dasar = 9600 mm
            instr.write_register(1045, section_parameters["size3"], functioncode=6)

            # Water level range (jarak sensor→dasar)
            # Sensor ke penampang atas = 700mm, tinggi penampang 2800mm
            # Jadi sensor→dasar = 700 + 2800 = 3500mm
            instr.write_register(
                1058, section_parameters["height_sensor"], functioncode=6
            )

            return True
        except Exception as e:
            print("❌ Gagal set section config:", e)
            return False
