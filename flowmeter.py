import crcmod
import time
import struct


class Flowmeter:
    def __init__(self, ser_ports, config):
        self.config = config
        self.ser_ports = ser_ports
        self.crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)

        # Terapkan konfigurasi penampang saat inisialisasi
        self.apply_section_configurations()

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
            if (
                device["type"] == "direct_rs485"
                and "section_parameters" in device
                and device["name"] == "Flowmeter"
            ):
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
