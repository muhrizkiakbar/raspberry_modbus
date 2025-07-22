import crcmod


class Wellpro:
    def __init__(self, ser_ports, config):
        self.config = config
        self.ser_ports = ser_ports
        self.crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)

    def read_analog(self, sensor_config, port):
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
