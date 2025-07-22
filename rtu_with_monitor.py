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
from dotenv import load_dotenv
import os


load_dotenv("/home/ftp/modbus/.env")
TELEMETRY_URL = "https://telemetry-adaro.id/api/key/telemetry"
API_KEY = "43fc6317-b9e7-4b5a-859c-a575d7e03fd6"
DEVICE_LOCATION_ID = int(os.getenv("DEVICE_LOCATION_ID"))


class RTU:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)
        self.ser_ports = self.init_serial_ports()
        self.mqtt_client = self.init_mqtt()
        self.crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
        self.restart_requested = False
        self.report_requested = False

    def load_config(self, _):
        url = f"https://telemetry-adaro.id/api/key/device_location/{DEVICE_LOCATION_ID}/config"
        headers = {
            "X-API-KEY": f"{API_KEY}",
            "Accept": "application/json",
        }
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Failed to load config from server: {e}")
            sys.exit(1)

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
                    "velocity": 0.0,
                    "water_volume": 0.0,
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
    gateway = RTU(None)
    gateway.monitor_all_devices()
