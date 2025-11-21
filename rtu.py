# rtu_main.py
import serial
import json
import time
import paho.mqtt.client as mqtt
import os
import sys
import subprocess
import requests
from dotenv import load_dotenv
from modbusampere import Modbusampere
from flowmeter import Flowmeter
from raincounterthread import RainCounterThread
from camera_stream import CameraStreamThread
import tempfile
import urllib3

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Makassar")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv("/home/ftp/modbus/.env")

TELEMETRY_URL = "https://telemetry-adaro.id/api/key/telemetry"
CONFIG_URL = "https://telemetry-adaro.id/api/key/device_location/{}/config"

DEVICE_LOCATION_ID = int(os.getenv("DEVICE_LOCATION_ID", ""))
API_KEY = str(os.getenv("API_KEY", ""))
MQTT_USERNAME = str(os.getenv("MQTT_USERNAME", ""))
MQTT_PASSWORD = str(os.getenv("MQTT_PASSWORD", ""))
RAINFALL_MM_PERPULSE = float(os.getenv("RAINFALL_MM_PERPULSE", 0.5))
SSL_CERT_PATH = "/home/pi/raspberry_modbus/telemetry-adaro.id.crt"

CAMERA_MODE = str(os.getenv("CAMERA_MODE", "OFF"))

VERSION = "1.0.17"


class RTU:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)
        self.photo_requested = False
        self.stream_requested = False
        self.report_requested = False
        self.restart_requested = False
        self.update_requested = False

        # Inisialisasi MQTT client terlebih dahulu
        self.mqtt_client = self.init_mqtt()

        # Inisialisasi camera thread dengan MQTT client
        self.camera_thread = CameraStreamThread(
            device_location_id=DEVICE_LOCATION_ID,
            api_key=API_KEY,
            mqtt_client=self.mqtt_client,
            mqtt_config=self.config["mqtt"],
        )

        if CAMERA_MODE == "CAMERA_ONLY":
            print("🎥 Mode: CAMERA_ONLY - sensor diabaikan")
            self.camera_thread.start()
            return
        elif CAMERA_MODE == "CAMERA_WITH_SENSORS":
            print("🎥📊 Mode: CAMERA_WITH_SENSORS - sensor dan kamera aktif")
            self.camera_thread.start()

        # Inisialisasi komponen sensor hanya jika bukan CAMERA_ONLY
        self.ser_ports = self.init_serial_ports()
        self.modbusampere = Modbusampere(self.ser_ports, self.config)
        self.flowmeter = Flowmeter(self.ser_ports, self.config)

        # === Rain Counter Thread ===
        rain_sensor = None
        rain_port = None
        for device in self.config["devices"]:
            if device["name"].lower() == "modbusampere":
                for sensor in device["sensors"]:
                    if sensor["name"].lower() == "rainfall":
                        rain_sensor = sensor
                        rain_port = device["port"]
                        break

        if rain_sensor:
            self.rain_thread = RainCounterThread(
                self.modbusampere,
                rain_sensor,
                rain_port,
                mm_per_pulse=RAINFALL_MM_PERPULSE,
                realtime_interval=5,
            )
            self.rain_thread.start()
        else:
            self.rain_thread = None

    def load_config(self, config_file):
        url = CONFIG_URL.format(DEVICE_LOCATION_ID)
        headers = {
            "X-API-KEY": API_KEY,
            "Accept": "application/json",
        }
        try:
            print(f"Ambil config dari API: {url}")
            response = requests.get(url, headers=headers, verify=False, timeout=10)
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
            # Subscribe ke topic command sensor
            client.subscribe(self.config["mqtt"]["command_topic"], qos=1)
            print(
                f"✅ Connected MQTT & Subscribed to {self.config['mqtt']['command_topic']}"
            )

            # Subscribe ke topic camera (akan dihandle oleh camera thread)
            camera_command_topic = f"{self.config['mqtt']['base_topic']}/camera/command"
            print(f"📡 Main RTU aware of camera topic: {camera_command_topic}")
        else:
            print(f"❌ Failed to connect MQTT: {reason_code}")
            return

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode().strip().lower()
        print(f"📨 Command MQTT diterima: '{payload}' dari topic: {msg.topic}")

        # Handle command dari topic sensor utama
        if msg.topic == self.config["mqtt"]["command_topic"]:
            if payload == "report":
                self.report_requested = True
            elif payload == "restart":
                self.restart_requested = True
            elif payload == "update":
                self.update_requested = True

        # Command camera dihandle oleh CameraStreamThread melalui topic terpisah
        # Tidak perlu handle di sini

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
                print("✅ Berhasil kirim data ke API")
            else:
                print(f"❌ Gagal kirim API: {response.status_code} {response.text}")

        except Exception as e:
            print(f"⚠️ Error kirim API: {e}")

    def handle_camera_commands(self):
        """Handle command kamera legacy (jika masih menggunakan topic lama)"""
        # Fungsi ini untuk backward compatibility
        # Sebaiknya gunakan topic camera terpisah
        if self.stream_requested:
            print("⚠️ Stream command via legacy topic, please use camera topic")
            self.stream_requested = False

        if self.photo_requested:
            print("⚠️ Photo command via legacy topic, please use camera topic")
            self.photo_requested = False

    def monitor_all_devices(self):
        try:
            while not self.restart_requested:
                # Handle legacy camera commands (jika ada)
                self.handle_camera_commands()

                if self.update_requested:
                    try:
                        print("Menjalankan git pull origin master...")
                        result = subprocess.run(
                            ["git", "pull", "origin", "master"],
                            capture_output=True,
                            text=True,
                        )
                        print(result.stdout)
                        if result.returncode == 0:
                            print("Git pull berhasil")
                            # Hentikan camera thread sebelum restart
                            if hasattr(self, "camera_thread"):
                                self.camera_thread.stop()
                            subprocess.run(["sudo", "reboot"], check=True)
                            print("Service modbus berhasil direstart")
                            break
                        else:
                            print("Git pull gagal:", result.stderr)
                    except Exception as e:
                        print("Error saat update:", e)
                    finally:
                        self.update_requested = False

                # Jika CAMERA_ONLY, skip pembacaan sensor
                if CAMERA_MODE == "CAMERA_ONLY":
                    time.sleep(5)
                    continue

                # Lanjutkan dengan pembacaan sensor untuk mode lainnya
                payload_mqtt = {
                    "timestamp": time.time(),
                    "timestamp_humanize": datetime.now(TZ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "device_location_id": DEVICE_LOCATION_ID,
                    "sensors": [],
                    "version": VERSION,
                }

                payload_api = {
                    "device_location_id": DEVICE_LOCATION_ID,
                    "ph": 0.0,
                    "tds": 0.0,
                    "tss": 0.0,
                    "debit": 0.0,
                    "rainfall": 0.0,
                    "rainfall_daily": 0.0,
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

                value_details = {}

                for device in self.config["devices"]:
                    port = device["port"]
                    for sensor in device["sensors"]:
                        value = None
                        if device["type"] == "modbus":
                            if sensor["type"] == "4-20mA":
                                value = self.modbusampere.read_analog(sensor, port)
                            elif sensor["type"] == "digital_in":
                                if self.rain_thread and sensor["name"] == "rainfall":
                                    value_details = {
                                        "realtime": self.rain_thread.rainfall_realtime,
                                        "daily": self.rain_thread.rainfall_daily,
                                        "hourly": self.rain_thread.rainfall_hourly,
                                        "total": self.rain_thread.rainfall_total,
                                        "unit": "mm",
                                    }
                                    value = self.rain_thread.rainfall_hourly
                                else:
                                    value = self.modbusampere.read_digital_inputs(
                                        sensor, port
                                    )
                        elif (
                            device["type"] == "direct_rs485"
                            and device["name"] == "rs_rad"
                        ):
                            value = self.flowmeter.read_sensor_data(sensor, port)

                        sensor_data = {}

                        if self.rain_thread and sensor["name"] == "rainfall":
                            print("kena di rainfall")
                            sensor_data = {
                                sensor["name"]: {
                                    "sensor_type": sensor["type"],
                                    "unit": sensor.get("conversion", {}).get(
                                        "unit", ""
                                    ),
                                    "value": round(value_details["realtime"], 1)
                                    if value_details["realtime"] is not None
                                    else "ERROR",
                                    "status": "OK" if value is not None else "error",
                                    "values": value_details,
                                }
                            }

                        else:
                            sensor_data = {
                                sensor["name"]: {
                                    "sensor_type": sensor["type"],
                                    "unit": sensor.get("conversion", {}).get(
                                        "unit", ""
                                    ),
                                    "value": round(value, 1)
                                    if value is not None
                                    else "ERROR",
                                    "status": "OK" if value is not None else "error",
                                    "value_details": value_details,
                                }
                            }

                        payload_mqtt["sensors"].append(sensor_data)

                        if value is not None and sensor["name"] in payload_api:
                            payload_api[sensor["name"]] = (
                                round(value, 1)
                                if isinstance(value, (int, float))
                                else int(value)
                            )

                            if self.rain_thread and sensor["name"] == "rainfall":
                                payload_api["rainfall_daily"] = (
                                    round(self.rain_thread.rainfall_daily, 1)
                                    if isinstance(
                                        self.rain_thread.rainfall_daily, (int, float)
                                    )
                                    else int(self.rain_thread.rainfall_daily)
                                )

                print(payload_mqtt)

                topic = self.config["mqtt"]["base_topic"]
                self.mqtt_client.publish(
                    topic, json.dumps(payload_mqtt), qos=self.config["mqtt"]["qos"]
                )

                # Kirim ke API jika ada perintah report
                if self.report_requested:
                    self.send_telemetry(payload_api)
                    self.report_requested = False

                time.sleep(5)

        except KeyboardInterrupt:
            print("🛑 Received interrupt, shutting down...")
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
        finally:
            print("🧹 Cleaning up...")
            # Hentikan semua thread
            if hasattr(self, "camera_thread"):
                self.camera_thread.stop()
            if hasattr(self, "rain_thread") and self.rain_thread:
                self.rain_thread.stop()
            print("✅ Cleanup completed")

        if self.restart_requested:
            print("🔁 Restart requested, keluar loop")
            # Hentikan semua thread sebelum restart
            if hasattr(self, "camera_thread"):
                self.camera_thread.stop()
            if hasattr(self, "rain_thread") and self.rain_thread:
                self.rain_thread.stop()
            subprocess.run(["sudo", "reboot"], check=True)


if __name__ == "__main__":
    gateway = RTU(None)
    gateway.monitor_all_devices()
