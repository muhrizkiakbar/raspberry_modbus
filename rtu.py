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
from flowmeter import Flowmeter
from raincounterthread import RainCounterThread
import tempfile

load_dotenv("/home/ftp/modbus/.env")

TELEMETRY_URL = "https://telemetry-adaro.id/api/key/telemetry"
CONFIG_URL = "https://telemetry-adaro.id/api/key/device_location/{}/config"

DEVICE_LOCATION_ID = int(os.getenv("DEVICE_LOCATION_ID", ""))
API_KEY = str(os.getenv("API_KEY", ""))
MQTT_USERNAME = str(os.getenv("MQTT_USERNAME", ""))
MQTT_PASSWORD = str(os.getenv("MQTT_PASSWORD", ""))
RAINFALL_MM_PERPULSE = float(os.getenv("RAINFALL_MM_PERPULSE", 0.2))

VERSION = "1.0.10"


class RTU:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)
        self.ser_ports = self.init_serial_ports()
        self.mqtt_client = self.init_mqtt()
        self.modbusampere = Modbusampere(self.ser_ports, self.config)
        self.flowmeter = Flowmeter(self.ser_ports, self.config)

        self.report_requested = False
        self.restart_requested = False
        self.update_requested = False

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
            # print("Connected to MQTT Broker")
            client.subscribe(self.config["mqtt"]["command_topic"], qos=1)
        else:
            # print(f"Failed to connect MQTT: {reason_code}")
            return

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
        # Root CA Certificate
        root_ca_cert = """-----BEGIN CERTIFICATE-----
            MIIGVzCCBT+gAwIBAgIMJUTYmj7dgxnQ27KzMA0GCSqGSIb3DQEBCwUAMFUxCzAJ
            BgNVBAYTAkJFMRkwFwYDVQQKExBHbG9iYWxTaWduIG52LXNhMSswKQYDVQQDEyJH
            bG9iYWxTaWduIEdDQyBSNiBBbHBoYVNTTCBDQSAyMDIzMB4XDTI1MDUyNzExNTIx
            NloXDTI2MDYyODExNTIxNVowHTEbMBkGA1UEAxMSdGVsZW1ldHJ5LWFkYXJvLmlk
            MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlV4BLTISN4HpOwKcc6Ah
            RbpclfwIeA10m7IoEegQ1t3VCTfo8ZuDBnJHUdvS7IONS50g+8Ry4lwSfo0eE8Jz
            zokDGHwM382/KndzPqndsI1Hp5M0971jOFHv81un+crDPHsExpzkW/jI+5ZiFgzb
            sNSzyiRoLIzITNWP2HvjWth012H+NkCVeaoMvjFIm9fLUkpQzrVL23tttF1Aee/z
            2FCJE4B2SWB3tR8ynaZZeCee8BRXmGtRPMYCCXowA4Xi/yKbM8l6BwimfRwXqFfb
            ovIr6LLNKeR+8UDKlcib7h2eYT/Qwvj12pCNhXlZKkf+PK/jVNNt50ncl1QRtez1
            KwIDAQABo4IDXTCCA1kwDgYDVR0PAQH/BAQDAgWgMAwGA1UdEwEB/wQCMAAwgZkG
            CCsGAQUFBwEBBIGMMIGJMEkGCCsGAQUFBzAChj1odHRwOi8vc2VjdXJlLmdsb2Jh
            bHNpZ24uY29tL2NhY2VydC9nc2djY3I2YWxwaGFzc2xjYTIwMjMuY3J0MDwGCCsG
            AQUFBzABhjBodHRwOi8vb2NzcC5nbG9iYWxzaWduLmNvbS9nc2djY3I2YWxwaGFz
            c2xjYTIwMjMwVwYDVR0gBFAwTjAIBgZngQwBAgEwQgYKKwYBBAGgMgoBAzA0MDIG
            CCsGAQUFBwIBFiZodHRwczovL3d3dy5nbG9iYWxzaWduLmNvbS9yZXBvc2l0b3J5
            LzBEBgNVHR8EPTA7MDmgN6A1hjNodHRwOi8vY3JsLmdsb2JhbHNpZ24uY29tL2dz
            Z2NjcjZhbHBoYXNzbGNhMjAyMy5jcmwwHQYDVR0RBBYwFIISdGVsZW1ldHJ5LWFk
            YXJvLmlkMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAfBgNVHSMEGDAW
            gBS9BbfzipM8c8t5+g+FEqF3lhiRdDAdBgNVHQ4EFgQUit2RzsDBNP4z6y8qbLzZ
            CILQodowggF+BgorBgEEAdZ5AgQCBIIBbgSCAWoBaAB3ABmG1Mcoqm/+ugNveCpN
            AZGqzi1yMQ+uzl1wQS0lTMfUAAABlxGWH8sAAAQDAEgwRgIhAM3mfIxWa7//bJOk
            Ggglpc2j1NtnB94jsh30SPPYyuYAAiEAsggqxRyb8VVuISdaVxRebt/RMvcXOqWq
            1F39Atyit/IAdQDLOPcViXyEoURfW8Hd+8lu8ppZzUcKaQWFsMsUwxRY5wAAAZcR
            lh/KAAAEAwBGMEQCIEcMJfrsDXoepgEqsjGYp7Mw4OEaqOvPiKUcFlQqRplNAiAX
            Gy6p+QNxhaqOkeixwCcE394rou7qFlmGdo59bd0SigB2ACUvlMIrKelun0Eacgcr
            aVxbUv+XqQ0lQLv83FHsTe4LAAABlxGWIRsAAAQDAEcwRQIhAOKX7mfik/1McLq8
            aidryEB9PJbLHnRHda/C8rpoQvVeAiBGmyhYsUAZtonmerye9Hyl6jpKoN5IhTp5
            +7r9mJKN8zANBgkqhkiG9w0BAQsFAAOCAQEAsGrhSzfw4wIq1sWaVvNXrXHaDv24
            cAMeMTqrSNg4VL/DYv5mlT2IQK+L7HllubaSh1h7pERy/u1kFvjDbksDVGiZe/rG
            6+n/jNO0t7zPD4VFsy5Ic+Qd1Wdla4KzM+f0xTwITIZMJdq+DOTST7VbGNOiaLS/
            lwllnoXbozJqz4NAlkcgVmkBo8NQaGOfn0jY2NP7YzPoZVRLNcYhw7b5zZKPdBCx
            1pAs81HK6eLGnCHCh71yWVoENxHzkreMUX+Ts/Vk9SP7VXmUXKQg9XKW0jjSvgsw
            g6AzbcEBUC/PvY6XkJF1NLf7pGi8g18KAM+yhsDTj35HJln6qlHqYNNpgA==
            -----END CERTIFICATE-----
            """
        try:
            headers = {
                "X-API-KEY": API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Simpan sementara sertifikat ke file
            with tempfile.NamedTemporaryFile(
                delete=False, mode="w", suffix=".crt"
            ) as ca_file:
                ca_file.write(root_ca_cert)
                ca_cert_path = ca_file.name

            # Gunakan verify untuk memverifikasi SSL dengan root CA ini
            response = requests.post(
                TELEMETRY_URL, json=payload_api, headers=headers, verify=ca_cert_path
            )

            if response.status_code == 200:
                print("✅ Berhasil kirim data ke API")
            else:
                print(f"❌ Gagal kirim API: {response.status_code} {response.text}")

        except Exception as e:
            print(f"⚠️ Error kirim API: {e}")

    def monitor_all_devices(self):
        while not self.restart_requested:
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

                        # Install package apt
                        # print("Menjalankan sudo apt install hello -y...")
                        # apt_result = subprocess.run(
                        #    ["sudo", "apt", "install", "hello", "-y"],
                        #    capture_output=True,
                        #    text=True,
                        # )
                        # if apt_result.returncode == 0:
                        #    print("Package hello berhasil diinstall")
                        # else:
                        #    print("Gagal install package hello:", apt_result.stderr)

                        # Install package pip
                        # pip_package = "somepackage"  # ganti sesuai kebutuhan
                        # print(
                        #    f"Menjalankan pip install {pip_package} --break-system-packages..."
                        # )
                        # pip_result = subprocess.run(
                        #    ["pip", "install", pip_package, "--break-system-packages"],
                        #    capture_output=True,
                        #    text=True,
                        # )
                        # if pip_result.returncode == 0:
                        #    print(f"Package {pip_package} berhasil diinstall via pip")
                        # else:
                        #    print(
                        #        f"Gagal install package {pip_package} via pip:",
                        #        pip_result.stderr,
                        #    )

                        # Restart service modbus
                        print("Restart service modbus...")
                        subprocess.run(
                            ["sudo", "systemctl", "restart", "modbus"], check=True
                        )
                        print("Service modbus berhasil direstart")
                        break  # keluar loop agar service restart sempurna
                    else:
                        print("Git pull gagal:", result.stderr)
                except Exception as e:
                    print("Error saat update:", e)
                finally:
                    self.update_requested = False

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
                        device["type"] == "direct_rs485" and device["name"] == "rs_rad"
                    ):
                        value = self.flowmeter.read_sensor_data(sensor, port)

                    sensor_data = {}

                    if self.rain_thread and sensor["name"] == "rainfall":
                        print("kena di rainfall")
                        sensor_data = {
                            sensor["name"]: {
                                "sensor_type": sensor["type"],
                                "unit": sensor.get("conversion", {}).get("unit", ""),
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
                                "unit": sensor.get("conversion", {}).get("unit", ""),
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
                            payload_api[sensor["rainfall_daily"]] = (
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

        print("Restart requested, keluar loop")


if __name__ == "__main__":
    gateway = RTU(None)
    gateway.monitor_all_devices()
