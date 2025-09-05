import serial
import json
import time
import paho.mqtt.client as mqtt
import os
import sys
import subprocess
from datetime import datetime
import requests
from dotenv import load_dotenv
from modbusampere import Modbusampere
from display import Display

load_dotenv("/home/ftp/modbus/.env")

TELEMETRY_URL = "https://telemetry-adaro.id/api/key/telemetry"
CONFIG_URL = "https://telemetry-adaro.id/api/key/device_location/{}/config"
DEVICE_LOCATION_ID = int(os.getenv("DEVICE_LOCATION_ID", ""))
API_KEY = str(os.getenv("API_KEY", ""))
MQTT_USERNAME = str(os.getenv("MQTT_USERNAME", ""))
MQTT_PASSWORD = str(os.getenv("MQTT_PASSWORD", ""))
VERSION = "1.0.3"


class RTU:
    def __init__(self, config_file="config.json"):
        self.config = self.load_config(config_file)
        self.ser_ports = self.init_serial_ports()
        self.mqtt_client = self.init_mqtt()
        self.modbusampere = Modbusampere(self.ser_ports, self.config)
        self.display = Display()

        self.report_requested = False
        self.restart_requested = False
        self.update_requested = False

    def load_config(self, config_file):
        url = CONFIG_URL.format(DEVICE_LOCATION_ID)
        headers = {
            "X-API-KEY": API_KEY,
            "Accept": "application/json",
        }
        try:
            print(f"Ambil config dari API: {url}")
            response = requests.get(url, headers=headers, verify="cert.pem", timeout=10)
            response.raise_for_status()
            config = response.json()
            print("Berhasil ambil config dari API")
            return config
        except Exception as e:
            print(f"Gagal ambil config API, fallback ke file lokal: {e}")
            try:
                with open(config_file) as f:
                    return json.load(f)
            except Exception as e2:
                print(f"Gagal load config lokal: {e2}")
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
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=conf["client_id"]
        )
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.connect(conf["broker"], conf["port"])
        client.loop_start()
        return client

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Connected to MQTT Broker")
            client.subscribe(self.config["mqtt"]["command_topic"], qos=1)
        else:
            print(f"Failed to connect MQTT: {reason_code}")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode().strip().lower()
        print(f"Command MQTT diterima: {payload}")
        if payload == "report":
            self.report_requested = True
        elif payload == "restart":
            self.restart_requested = True
        elif payload == "update":
            self.update_requested = True

    def send_telemetry(self, payload_api):
        try:
            headers = {
                "X-API-KEY": API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            response = requests.post(
                TELEMETRY_URL, json=payload_api, headers=headers, verify=False
            )
            if response.status_code == 200:
                print("Berhasil kirim data ke API")
            else:
                print(f"Gagal kirim API: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Error kirim API: {e}")

    def monitor_all_devices(self):
        current_page = 0
        last_change = time.time()
        while not self.restart_requested:
            now = time.time()
            time_left = 20 - int(now - last_change)

            if self.update_requested:
                print("==================== UPDATING ==============================")
                try:
                    print("Menjalankan git pull origin master...")
                    result = subprocess.run(
                        ["git", "pull", "origin", "master"],
                        capture_output=True,
                        text=True,
                    )
                    print(result.stdout)
                    if result.returncode == 0:
                        print("Git pull berhasil, restart service...")
                        # Restart service (misal systemd service 'modbus')
                        subprocess.run(
                            ["sudo", "systemctl", "restart", "modbus"], check=True
                        )
                        print("Service modbus berhasil direstart")
                        # Hentikan loop untuk memastikan restart sempurna
                        break
                    else:
                        print("Git pull gagal:", result.stderr)
                except Exception as e:
                    print("Error saat update:", e)
                finally:
                    self.update_requested = False
                print(
                    "==================== END UPDATING =============================="
                )

            payload_mqtt = {
                "timestamp": time.time(),
                "timestamp_humanize": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "device_location_id": DEVICE_LOCATION_ID,
                "sensors": [],
                "version": VERSION,
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

            for device in self.config["devices"]:
                port = device["port"]
                for sensor in device["sensors"]:
                    value = None
                    if sensor["type"] == "4-20mA":
                        value = self.modbusampere.read_analog(sensor, port)
                    elif sensor["type"] == "digital_in":
                        value = self.modbusampere.read_digital_inputs(sensor, port)

                    sensor_data = {
                        sensor["name"]: {
                            "sensor_type": sensor["type"],
                            "unit": sensor.get("conversion", {}).get("unit", ""),
                            "value": round(value, 1),
                            "status": "OK" if value is not None else "ERROR",
                        }
                    }
                    payload_mqtt["sensors"].append(sensor_data)

                    if value is not None and sensor["name"] in payload_api:
                        payload_api[sensor["name"]] = (
                            round(float(value), 1)
                            if isinstance(value, (int, float))
                            else int(value)
                        )

            # Publish ke MQTT
            if payload_mqtt["sensors"]:
                page_count = (len(payload_mqtt["sensors"]) + 5) // 6

                print("****************************************")
                print(payload_mqtt["sensors"])
                print("****************************************")
                self.display.display_sensor_page(
                    payload_mqtt["sensors"], current_page, time_left
                )

                if now - last_change >= 20:
                    last_change = now
                    current_page = (current_page + 1) % page_count
                topic = self.config["mqtt"]["base_topic"]
                self.mqtt_client.publish(
                    topic, json.dumps(payload_mqtt), qos=self.config["mqtt"]["qos"]
                )
                print("MQTT Payload:", payload_mqtt)

            # Kirim ke API jika ada perintah report
            if self.report_requested:
                print("==================== REPORTING ==============================")
                print("Command report diterima → kirim API...")
                self.send_telemetry(payload_api)
                self.report_requested = False
                print(
                    "==================== END REPORTING =============================="
                )

            time.sleep(5)

        print("Restart requested, keluar loop")


if __name__ == "__main__":
    gateway = RTU("config.json")
    gateway.monitor_all_devices()
