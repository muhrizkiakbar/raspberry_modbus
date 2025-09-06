import minimalmodbus
import serial


class Modbusampere:
    def __init__(self, ser_ports, config):
        self.ser_ports = ser_ports
        self.config = config
        self.instruments = {}
        print("==================================")
        print(config["devices"])
        print("==================================")

        for device in config["devices"]:
            if "Wellpro" in device["name"]:
                port = device["port"]
                for sensor in device["sensors"]:
                    slave_addr = sensor["slave_address"]
                    key = f"{port}_{slave_addr}"
                    print("==================================")
                    print("key")
                    print(key)
                    print("==================================")
                    if key not in self.instruments:
                        instr = minimalmodbus.Instrument(port, slave_addr)
                        instr.serial.baudrate = ser_ports[port].baudrate
                        instr.serial.bytesize = ser_ports[port].bytesize
                        instr.serial.parity = ser_ports[port].parity
                        instr.serial.stopbits = ser_ports[port].stopbits
                        instr.serial.timeout = 1
                        instr.mode = minimalmodbus.MODE_RTU
                        self.instruments[key] = instr

    # Analog 4-20mA
    def read_analog(self, sensor, port):
        slave_addr = sensor["slave_address"]
        channel = sensor["channel"]
        key = f"{port}_{slave_addr}"
        instr = self.instruments[key]
        try:
            values = instr.read_registers(0, 6, functioncode=3)
            raw = values[channel]
            current_ma = raw * 20.0 / 4095.0
            conv = sensor["conversion"]
            scaled = (current_ma - conv["input_min"]) / (
                conv["input_max"] - conv["input_min"]
            ) * (conv["output_max"] - conv["output_min"]) + conv["output_min"]
            return max(conv["output_min"], min(scaled, conv["output_max"]))
        except Exception as e:
            print(f"Error baca analog {sensor['name']}: {e}")
            return None

    # Digital Input
    def read_digital_inputs(self, sensor, port):
        slave_addr = sensor["slave_address"]
        channel = sensor["channel"]
        key = f"{port}_{slave_addr}"
        instr = self.instruments[key]
        try:
            bits = instr.read_bits(0, 4, functioncode=2)
            return bool(bits[channel])
        except Exception as e:
            print(f"Error baca DI {sensor['name']}: {e}")
            return None
