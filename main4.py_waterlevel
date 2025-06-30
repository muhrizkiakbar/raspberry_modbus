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

# Konfigurasi API Telemetry
TELEMETRY_URL = "https://telemetry-adaro.id/api/key/telemetry"
API_KEY = "43fc6317-b9e7-4b5a-859c-a575d7e03fd6"
DEVICE_LOCATION_ID = 89


class IndustrialGateway:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)
        self.ser_ports = self.init_serial_ports()
        self.mqtt_client = self.init_mqtt()
        self.crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
        self.restart_requested = False
        self.report_requested = False

        # Terapkan konfigurasi penampang saat inisialisasi
        self.apply_section_configurations()

    def load_config(self, file_path):
        with open(file_path, "r") as f:
            return json.load(f)

    def init_serial_ports(self):
        ports = {}
        print("\nInitializing serial ports:")
        for port, params in self.config["serial_ports"].items():
            try:
                print(f"  - {port}: {params['description']}")
                print(
                    f"    Baudrate: {params['baudrate']}, Parity: {params['parity']}, Stopbits: {params['stopbits']}"
                )

                ser = serial.Serial(
                    port=port,
                    baudrate=params["baudrate"],
                    bytesize=params["bytesize"],
                    parity=params["parity"],
                    stopbits=params["stopbits"],
                    timeout=2,
                )

                # Test port connection
                ser.write(b"")  # Test write
                print(f"    ✅ Port opened successfully")

                ports[port] = ser
            except Exception as e:
                print(f"    ❌ Error initializing port: {str(e)}")
                ports[port] = None

        print("Serial port initialization complete\n")
        return ports

    def init_mqtt(self):
        conf = self.config["mqtt"]
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=conf["client_id"]
        )
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
                "X-API-KEY": API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            response = requests.post(
                TELEMETRY_URL, json=payload, headers=headers, verify=False
            )

            if response.status_code == 200:
                print("Berhasil mengirim data ke API")
                return True
            else:
                print(f"Gagal mengirim data: {response.status_code}")
                return False
        except Exception as e:
            print(f"Exception in send_telemetry: {str(e)}")
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
                print("\nReceived report command via MQTT")
                self.report_requested = True

    def modbus_request(self, port, slave, function_code, address, count=1):
        """Send Modbus request and read response"""
        if port not in self.ser_ports or self.ser_ports[port] is None:
            print(f"Port {port} not available")
            return None

        # Format request frame
        frame = struct.pack(">B B H H", slave, function_code, address, count)
        crc = self.crc16(frame).to_bytes(2, "little")
        request = frame + crc

        try:
            # Clear buffers
            self.ser_ports[port].reset_input_buffer()
            self.ser_ports[port].reset_output_buffer()

            # Debug: print request
            print(f"\n[DEBUG] Request: {request.hex().upper()}")

            # Send request
            self.ser_ports[port].write(request)

            # Calculate expected response length
            # Response: [slave(1), func(1), byte count(1)] + [data(2*count)] + [CRC(2)]
            expected_length = 5 + 2 * count

            # Read with longer timeout
            response = b""
            start_time = time.time()
            while len(response) < expected_length and (time.time() - start_time) < 2.0:
                response += self.ser_ports[port].read(expected_length - len(response))

            if not response:
                print("[DEBUG] No response received")
                return None

            print(f"[DEBUG] Response: {response.hex().upper()} ({len(response)} bytes)")

            # Verify minimum response length
            if len(response) < 5:
                print(f"Response too short: {len(response)} bytes")
                return None

            # Verify CRC
            response_crc = int.from_bytes(response[-2:], "little")
            calculated_crc = self.crc16(response[:-2])

            if calculated_crc != response_crc:
                print(
                    f"CRC error: Calculated {hex(calculated_crc)}, Received {hex(response_crc)}"
                )
                return None

            # Return data part
            return response[3:-2]
        except Exception as e:
            print(f"Exception in modbus_request: {str(e)}")
            return None

    def reset_water_volume(self, port, slave_address):
        """Reset water volume counter"""
        # Register 40001: Clear current water volume
        self.write_register(port, slave_address, 40001, 0x5A5A)

    def read_rs485_direct(self, sensor_config, device_port):
        """Read value from RS485 direct sensor"""
        # Tentukan jumlah register yang dibaca
        if sensor_config["conversion"]["register_type"] == "32bit_int":
            count = 2
        else:
            count = 1  # Default 16-bit

        response = self.modbus_request(
            device_port,
            sensor_config["slave_address"],
            0x03,
            sensor_config["register_address"],
            count,
        )

        if not response:
            return None

        conv = sensor_config["conversion"]

        if conv["register_type"] == "16bit_int":
            raw_value = struct.unpack(">H", response)[0]
            return raw_value * conv["scaling_factor"]
        elif conv["register_type"] == "32bit_int":
            # Gabungkan 2 register menjadi 1 nilai 32-bit
            raw_value = struct.unpack(">I", response)[0]
            return raw_value * conv["scaling_factor"]
        else:
            print(f"Unsupported register type: {conv['register_type']}")
            return None

    def write_register(self, port, slave, address, value):
        """Write a single Modbus register"""
        if port not in self.ser_ports or self.ser_ports[port] is None:
            print(f"Port {port} not available")
            return False

        # Pack the Modbus frame
        frame = struct.pack(
            ">B B H H",
            slave,
            0x06,  # Function 06: Write single register
            address,
            value,
        )
        crc = self.crc16(frame).to_bytes(2, "little")
        request = frame + crc

        try:
            self.ser_ports[port].flushInput()
            print(
                f"Writing to register: slave={slave}, address={address}, value={value}"
            )
            print(f"Request hex: {request.hex()}")

            self.ser_ports[port].write(request)
            time.sleep(0.5)  # Beri waktu lebih lama untuk respons

            # Read response (8 bytes expected)
            response = self.ser_ports[port].read(8)

            if len(response) == 0:
                print("Error: No response from device")
                return False

            print(f"Response hex: {response.hex()}")

            if len(response) != 8:
                print(f"Write register response too short: {len(response)} bytes")
                return False

            # Verify CRC
            response_crc = int.from_bytes(response[-2:], "little")
            calculated_crc = self.crc16(response[:-2])

            if calculated_crc != response_crc:
                print(
                    f"CRC error: Calculated {hex(calculated_crc)}, Received {hex(response_crc)}"
                )
                return False

            # Verify echoed data
            if response[:6] != request[:6]:
                print("Echoed data mismatch")
                print(f"Sent: {request[:6].hex()}")
                print(f"Received: {response[:6].hex()}")
                return False

            return True
        except Exception as e:
            print(f"Exception in write_register: {str(e)}")
            return False

    def configure_channel_section(self, port, slave_address, params):
        """Configure channel section parameters on the flow meter"""
        # Register addresses (decimal)
        SECTION_TYPE_REG = 41043  # 0x0412H
        SECTION_SIZE1_REG = 41044  # 0x0413H
        SECTION_SIZE2_REG = 41045  # 0x0414H
        SECTION_SIZE3_REG = 41046  # 0x0415H

        print(
            f"Configuring section: Type={params['section_type']}, "
            f"Sizes={params['size1']}/{params['size2']}/{params['size3']}mm"
        )

        # Set section type
        if not self.write_register(
            port, slave_address, SECTION_TYPE_REG, params["section_type"]
        ):
            print("Error writing section type")
            return False

        # Set section size 1 (channel height)
        if not self.write_register(
            port, slave_address, SECTION_SIZE1_REG, params["size1"]
        ):
            print("Error writing size1")
            return False

        # For trapezoid, set size2 (slope width)
        if params["section_type"] == 1:  # trapezoid
            if not self.write_register(
                port, slave_address, SECTION_SIZE2_REG, params["size2"]
            ):
                print("Error writing size2")
                return False

        # Set section size 3 (bottom width)
        if not self.write_register(
            port, slave_address, SECTION_SIZE3_REG, params["size3"]
        ):
            print("Error writing size3")
            return False

        print("Section configuration successful!")
        return True

    def test_communication(self, port, slave_address):
        """Test basic communication by reading a register"""
        try:
            print("\n[TEST] Starting communication test...")
            print(f"Port: {port}, Slave address: {slave_address}")

            # Coba baca register yang selalu ada, misalnya water level (41003)
            print("Trying to read water level register (1003)...")
            response = self.modbus_request(
                port,
                slave_address,
                0x03,  # Read holding registers
                1003,  # Water level register (decimal address)
                1,  # Read 1 register
            )

            if response:
                value = struct.unpack(">H", response)[0]
                print(f"✅ Success! Read water level value: {value} mm")
                return True
            else:
                print("❌ Failed to read from device")

                # Coba baca register lain sebagai alternatif
                print("Trying alternative register (1002 - Instantaneous Flow)...")
                response = self.modbus_request(
                    port,
                    slave_address,
                    0x03,
                    1002,  # Instantaneous flow register
                    1,
                )

                if response:
                    value = struct.unpack(">H", response)[0]
                    print(f"✅ Success with alternative register! Value: {value}")
                    return True
                else:
                    print("❌ Failed with alternative register too")
                    return False
        except Exception as e:
            print(f"Communication test error: {str(e)}")
            return False

    def apply_section_configurations(self):
        """Apply section configurations for all direct_rs485 devices"""
        for device in self.config["devices"]:
            if device["type"] == "direct_rs485" and "section_parameters" in device:
                port = device["port"]

                # Periksa apakah port tersedia
                if port not in self.ser_ports:
                    print(f"⚠️ Port {port} not defined in serial ports configuration")
                    continue

                if self.ser_ports[port] is None:
                    print(f"⚠️ Port {port} initialization failed earlier")
                    continue

                # Gunakan alamat slave dari sensor pertama
                slave_address = device["sensors"][0]["slave_address"]
                params = device["section_parameters"]

                print(f"\n{'=' * 50}")
                print(f"Configuring device: {device['name']}")
                print(f"Port: {port}, Slave address: {slave_address}")

                # Pertama, tes komunikasi dasar
                if not self.test_communication(port, slave_address):
                    print(f"❌ Basic communication test failed for {device['name']}")

                    # Coba dengan alamat slave alternatif
                    print("Trying with common slave addresses...")
                    for alt_addr in [1, 2, 3, 4, 5, 10, 20, 50]:
                        print(f"Trying slave address {alt_addr}...")
                        if self.test_communication(port, alt_addr):
                            print(f"✅ Found working slave address: {alt_addr}")
                            # Update slave address in config
                            for sensor in device["sensors"]:
                                sensor["slave_address"] = alt_addr
                            slave_address = alt_addr
                            break
                    else:
                        print("❌ No working slave address found")
                        continue

                # Jika komunikasi berhasil, lanjut konfigurasi
                success = self.configure_channel_section(port, slave_address, params)

                if success:
                    print(f"✅ {device['name']} section config applied")
                else:
                    print(f"❌ Failed to configure {device['name']}")

                print(f"{'=' * 50}\n")
                time.sleep(1)

    def graceful_shutdown(self):
        print("\nPerforming graceful shutdown...")
        for port in self.ser_ports.values():
            if port is not None:
                port.close()
        self.mqtt_client.disconnect()
        print("All resources cleaned up")

    def restart_application(self):
        self.graceful_shutdown()
        print("\nRestarting application...")
        python = sys.executable
        os.execl(python, python, *sys.argv)

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
                    "water_volume": 0.0,
                }

                # Baca semua sensor
                for device in self.config["devices"]:
                    device_port = device["port"]

                    # Skip if port not available
                    if (
                        device_port not in self.ser_ports
                        or self.ser_ports[device_port] is None
                    ):
                        continue

                    for sensor in device["sensors"]:
                        value = None

                        if device["type"] == "direct_rs485":
                            value = self.read_rs485_direct(sensor, device_port)

                        # Membuat entri data sensor
                        sensor_data = {
                            "name": sensor["name"],
                            "sensor_type": sensor["type"],
                            "unit": sensor["conversion"].get("unit", ""),
                        }

                        if value is not None:
                            sensor_data["value"] = value
                            sensor_data["status"] = "OK"
                            # Untuk API Telemetry, kita masukkan ke payload_api jika nama sesuai
                            # Misal: sensor name "Instantaneous Flow" -> debit
                            if sensor["name"] == "Instantaneous Flow":
                                payload_api["debit"] = value
                            elif sensor["name"] == "Water Level":
                                payload_api["water_height"] = value
                            elif sensor["name"] == "Water Volume":
                                payload_api["water_volume"] = value
                        else:
                            sensor_data["value"] = None
                            sensor_data["error"] = "Gagal membaca sensor"
                            sensor_data["status"] = "ERROR"

                        payload["sensors"].append(sensor_data)
                        time.sleep(0.2)

                # Publish ke MQTT
                topic = f"{self.config['mqtt']['base_topic']}"
                self.mqtt_client.publish(
                    topic, json.dumps(payload), qos=self.config["mqtt"]["qos"]
                )
                print(f"Published to MQTT topic {payload}")
                print(f"Published to MQTT topic {topic}")

                # Jika ada permintaan report atau kondisi lainnya, kirim ke telemetry API
                if self.report_requested:
                    print("Sending telemetry to API...")
                    self.send_telemetry(payload_api)
                    self.report_requested = False  # Reset setelah dikirim

                time.sleep(2)  # Interval pembacaan

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
