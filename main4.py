import serial
import crcmod
import json
import time
import struct
import paho.mqtt.client as mqtt
import os
import sys
from datetime import datetime
import requests


TELEMETRY_URL = "https://telemetry-adaro.id/api/key/telemetry"
API_KEY = "43fc6317-b9e7-4b5a-859c-a575d7e03fd6"
DEVICE_LOCATION_ID = 8


class IndustrialGateway:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)
        self.ser_ports = self.init_serial_ports()
        self.mqtt_client = self.init_mqtt()
        self.crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
        self.restart_requested = False
        self.report_requested = False

    def load_config(self, file_path):
        with open(file_path, "r") as f:
            return json.load(f)

    def init_serial_ports(self):
        ports = {}
        for port, params in self.config["serial_ports"].items():
            ports[port] = serial.Serial(
                port=port,
                baudrate=params["baudrate"],
                bytesize=params["bytesize"],
                parity=params["parity"],
                stopbits=params["stopbits"],
                timeout=1,
            )
        return ports

    def init_mqtt(self):
        conf = self.config["mqtt"]
        print(conf)
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="")
        client.username_pw_set("belerang", "Gj8Q4sOQ%LFA6#belerang")
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.connect(conf["broker"], conf["port"])
        client.loop_start()
        return client

    def send_telemetry(self, payload):
        """Send sensor data to telemetry API"""

        try:
            headers = {
                "X-API-KEY": f"{API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            response = requests.post(
                TELEMETRY_URL, json=payload, headers=headers, verify=False
            )

            if response.status_code == 200:
                self.report_requested = False
                print("Berhasil mengirim data ke API")
                return True
            else:
                print(response.status_code)
                return False

        except Exception as e:
            return False

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Connected to MQTT Broker!")
            client.subscribe(self.config["mqtt"]["command_topic"], qos=1)
        else:
            print(f"Failed to connect to MQTT, reason code: {reason_code}")

    def on_message(self, client, userdata, msg):
        if msg.topic == self.config["mqtt"]["command_topic"]:
            payload = msg.payload.decode().strip().lower()
            if payload == "restart":
                print("\nReceived restart command via MQTT")
                self.restart_requested = True
            elif payload == "report":
                self.report_requested = True

    def modbus_request(self, port, slave, function_code, address, count=1):
        frame = bytes(
            [
                slave,
                function_code,
                (address >> 8) & 0xFF,
                address & 0xFF,
                (count >> 8) & 0xFF,
                count & 0xFF,
            ]
        )
        crc = self.crc16(frame).to_bytes(2, "little")
        request = frame + crc

        self.ser_ports[port].write(request)

        expected_length = 5 + 2 * count + 2  # Header + Data + CRC
        response = self.ser_ports[port].read(expected_length)

        if len(response) != expected_length:
            return None

        if self.crc16(response[:-2]) != int.from_bytes(response[-2:], "little"):
            return None

        return response[3:-2]

    def read_analog(self, port, sensor_config):
        # raw_data = self.modbus_request(
        #    port,
        #    sensor_config["slave_address"],
        #    0x03,
        #    sensor_config["channel"],
        # )

        # if not raw_data:
        #    return None

        # raw_value = struct.unpack(">H", raw_data)[0]

        frame = bytes(
            [
                sensor_config["slave_address"],
                0x03,
                (sensor_config["channel"] >> 8) & 0xFF,
                sensor_config["channel"] & 0xFF,
                0x00,
                0x01,
            ]
        )
        crc = self.crc16(frame).to_bytes(2, "little")
        request = frame + crc
        self.ser_ports[port].write(request)
        response = self.ser_ports[port].read(7)

        conv = sensor_config["conversion"]

        if len(response) == 7:
            if sensor_config["type"] == "4-20mA":
                raw_value = int.from_bytes(response[3:5], "big")
                current = (raw_value * 20) / 4095
                return (current - conv["input_min"]) * (
                    conv["output_max"] - conv["output_min"]
                ) / (conv["input_max"] - conv["input_min"]) + conv["output_min"]
            elif sensor_config["type"] == "0-5V":
                # harus dicek lagi
                raw_value = int.from_bytes(response[3:5], "big")
                voltage = (raw_value * 5.0) / 4095.0
                return (voltage - conv["input_min"]) * (
                    conv["output_max"] - conv["output_min"]
                ) / (conv["input_max"] - conv["input_min"]) + conv["output_min"]
        else:
            print(f"[{sensor_config['name']}] ERROR: Respons tidak lengkap!")

    def read_digital_input(self, sensor_config):
        response = self.modbus_request(
            sensor_config["port"],
            sensor_config["slave_address"],
            0x02,  # Function code for read discrete inputs
            sensor_config["address"],
        )
        return struct.unpack(">H", response)[0] if response else None

    def read_rs485_direct(self, sensor_config):
        response = self.modbus_request(
            sensor_config["port"],
            sensor_config["slave_address"],
            0x03,
            sensor_config["register_address"],
        )

        if not response:
            return None

        conv = sensor_config["conversion"]
        if conv["register_type"] == "32bit_float":
            return struct.unpack(">f", response)[0] * conv["scaling_factor"]
        elif conv["register_type"] == "16bit_int":
            return struct.unpack(">H", response)[0] * conv["scaling_factor"]

    def graceful_shutdown(self):
        print("\nPerforming graceful shutdown...")
        for port in self.ser_ports.values():
            port.close()
        self.mqtt_client.disconnect()
        print("All resources cleaned up")

    def restart_application(self):
        self.graceful_shutdown()
        print("\nRestarting application...")
        python = sys.executable

    def monitor_all_devices(self):
        try:
            while not self.restart_requested:
                payload = {
                    "timestamp": time.time(),
                    "timestamp_humanize": datetime.fromtimestamp(time.time()).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "device_location_id": DEVICE_LOCATION_ID,
                    "sensors": [],
                }

                payload_api = {
                    "device_location_id": DEVICE_LOCATION_ID,
                    "ph": 0.0,
                    "tds": 0.0,
                    "debit": 0.0,
                    "rainfall": 0.0,
                    "water_height": 0.0,
                    "temperature": 0.0,
                    "humidity": 0.0,
                    "wind_direction": 0.0,
                    "wind_speed": 0.0,
                    "solar_radiation": 0.0,
                    "evaporation": 0.0,
                    "dissolve_oxygen": 0.0,
                }

                # Baca semua sensor terlebih dahulu
                for device in self.config["devices"]:
                    device_port = device["port"]

                    for sensor in device["sensors"]:
                        value = None

                        # Membaca nilai sensor
                        if device["type"] == "analog_io":
                            value = self.read_analog(device_port, sensor)
                        elif device["type"] == "digital_io":
                            if sensor["type"] == "digital_in":
                                value = self.read_digital_input(sensor)
                        elif device["type"] == "direct_rs485":
                            value = self.read_rs485_direct(sensor)

                        # Membuat entri data sensor
                        sensor_data = {
                            sensor["name"]: {
                                "sensor_type": sensor["type"],
                                "unit": sensor["conversion"].get("unit", ""),
                            }
                        }

                        if value is not None and value >= 0:
                            payload_api[sensor["name"]] = float(value)
                            sensor_data[sensor["name"]]["value"] = float(value)
                            sensor_data[sensor["name"]]["status"] = "OK"
                        else:
                            sensor_data[sensor["name"]]["value"] = None
                            sensor_data[sensor["name"]]["error"] = (
                                "Gagal membaca sensor"
                            )
                            sensor_data[sensor["name"]]["status"] = "ERROR"

                        payload["sensors"].append(sensor_data)
                        time.sleep(0.2)

                # Publish semua data sekaligus
                print(payload)
                if payload["sensors"]:
                    topic = f"{self.config['mqtt']['base_topic']}"
                    self.mqtt_client.publish(
                        topic, json.dumps(payload), qos=self.config["mqtt"]["qos"]
                    )

                if self.report_requested:
                    print("report diterima")
                else:
                    print("report belum diterima")

                if self.report_requested:
                    print("======================================================")
                    print(payload_api)
                    print("======================================================")
                    self.send_telemetry(payload_api)

                time.sleep(2)

            time.sleep(5)

            if self.restart_requested:
                self.restart_application()

        except KeyboardInterrupt:
            self.graceful_shutdown()
            print("\nAplikasi dihentikan oleh pengguna")

        except Exception as e:
            print(f"Error kritis: {str(e)}")
            self.restart_application()


if __name__ == "__main__":
    gateway = IndustrialGateway("sensors_config.json")
    gateway.monitor_all_devices()
