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
        self.lock = threading.Lock()

        # Data & waktu terakhir tiap sensor
        self.sensor_data = {
            "debit": {"value": 0, "time": 0},
            "water_height": {"value": 0, "time": 0},
            "velocity": {"value": 0, "time": 0},
        }

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
                instr.serial.timeout = 3
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
        name = sensor["name"]
        instr = self.instruments[self.last_key]

        with self.lock:
            now = time.time()
            last_time = self.sensor_data[name]["time"]

            # kalau belum 60 detik, return cached value
            if now - last_time < 60:
                return self.sensor_data[name]["value"]

            # sudah lewat 60 detik -> baca ulang
            try:
                if name == "water_height":
                    depth_info = instr.read_register(1003, 0, functioncode=3)
                    if depth_info:
                        val = depth_info / 1000.0
                        if val == 0:
                            return self.sensor_data[name]["value"]

                        self.sensor_data[name] = {"value": val, "time": now}
                        return val

                elif name == "velocity":
                    velocity_cms = instr.read_register(1004, 0, functioncode=3)
                    val = velocity_cms
                    if val == 0:
                        return self.sensor_data[name]["value"]
                    self.sensor_data[name] = {"value": val, "time": now}
                    return val

                elif name == "debit":
                    flow_raw = instr.read_register(1002, 0, functioncode=3)
                    val = flow_raw / 1000.0
                    if val == 0:
                        return self.sensor_data[name]["value"]
                    self.sensor_data[name] = {"value": val, "time": now}
                    return val

            except Exception as e:
                print(f"❌ Gagal baca {name}:", e)
                return self.sensor_data[name]["value"]

    def set_section_config(self, instr, section_parameters):
        try:
            print("=========================instr")
            print(instr)
            print("=========================instr")

            instr.write_register(
                1042, section_parameters["section_type"], functioncode=6
            )
            instr.write_register(1043, section_parameters["size1"], functioncode=6)
            instr.write_register(1044, section_parameters["size2"], functioncode=6)
            instr.write_register(1045, section_parameters["size3"], functioncode=6)
            instr.write_register(
                1058, section_parameters["height_sensor"], functioncode=6
            )
            return True
        except Exception as e:
            print("❌ Gagal set section config:", e)
            return False
