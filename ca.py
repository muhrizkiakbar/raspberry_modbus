import minimalmodbus

instrument = minimalmodbus.Instrument("/dev/ttyUSB1", 1)  # (port, slave address)
instrument.serial.baudrate = 4800
instrument.serial.bytesize = 8
instrument.serial.parity = "N"
instrument.serial.stopbits = 1
instrument.serial.timeout = 1

try:
    # Baca 1 register di alamat 1003 (decimal)
    water_level = instrument.read_register(
        1003, 0, 3
    )  # (address, decimals, functioncode=3)
    print("Water Level:", 65535 - water_level, "mm")
except Exception as e:
    print("❌ Error:", e)
