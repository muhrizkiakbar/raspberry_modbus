from sys import set_coroutine_origin_tracking_depth
import crcmod
import time
import struct
import minimalmodbus


class Flowmeter:
    def __init__(self, ser_ports, config):
        self.config = config
        self.ser_ports = ser_ports
        self.instruments = {}
        self.last_key = ""

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
                for sensor in device["sensors"]:
                    slave_addr = sensor["slave_address"]
                    key = f"{port}_{slave_addr}"
                    if key not in self.instruments:
                        instr = minimalmodbus.Instrument(port, slave_addr)
                        instr.serial.baudrate = ser_ports[port].baudrate
                        instr.serial.bytesize = ser_ports[port].bytesize
                        instr.serial.parity = ser_ports[port].parity
                        instr.serial.stopbits = ser_ports[port].stopbits
                        instr.serial.timeout = 1
                        instr.mode = minimalmodbus.MODE_RTU
                        self.last_key = key
                        self.instruments[key] = instr

                self.set_section_config(
                    self.instruments[self.last_key], device["section_parameters"]
                )

    def read_sensor_data(self, sensor, port):
        """Baca semua data sensor"""
        instr = self.instruments[self.last_key]

        if sensor["name"] == "water_height":
            try:
                # Register 1003 = current water level (permukaan air→dasar penampang, mm)
                depth_info = instr.read_register(1003, 0, functioncode=3)
                if depth_info:
                    # will return mm
                    return depth_info
            except Exception as e:
                print("❌ Gagal baca Water Level:", e)

        if sensor["name"] == "velocity":
            try:
                # Velocity (0x03EC = 1004) -> cm/s
                velocity_cms = instr.read_register(1004, 0, functioncode=3)
                # will return cms
                # data["velocity_cms"] = velocity_cms
                return velocity_cms
                # will return ms
                # data["velocity_ms"] = velocity_cms / 100.0
            except Exception as e:
                print("❌ Gagal baca Velocity:", e)

        if sensor["name"] == "debit":
            try:
                # Instantaneous Flow (0x03EA = 1002) -> m³/s * 1000
                flow_raw = instr.read_register(1002, 0, functioncode=3)
                # will return m3s
                # data["flow_m3s"] = flow_raw / 1000.0
                return flow_raw / 1000.0
            except Exception as e:
                print("❌ Gagal baca Flow:", e)

    def set_section_config(self, key, section_parameters):
        """Konfigurasi penampang trapezoid sesuai data Anda"""
        try:
            instr = self.instruments[key]

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
