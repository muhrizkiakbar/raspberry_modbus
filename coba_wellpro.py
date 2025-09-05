import minimalmodbus
import serial

# Konfigurasi koneksi
instrument = minimalmodbus.Instrument(
    "/dev/ttyUSB0", 1
)  # port serial RS485, slave address=1
instrument.serial.baudrate = 9600
instrument.serial.bytesize = 8
instrument.serial.parity = serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 1  # detik

instrument.mode = minimalmodbus.MODE_RTU


# === Membaca Analog Input (0-20mA, 6 channel) ===
def read_analog_channels():
    # Register mulai dari 0x0000, jumlah 6 register
    values = instrument.read_registers(0, 6, functioncode=3)
    currents = []
    for raw in values:
        # Konversi sesuai manual: I = DATA * 20 / 4095 (mA)
        current = raw * 20.0 / 4095.0
        print("=============raw")
        print(raw)
        print("=============raw")
        current = (raw * 20) / 4095
        nilai_ph = (current - 4) * (14 - 1) / (20 - 4) + 1
        currents.append(round(nilai_ph, 3))
    return currents


# === Membaca Digital Input (4 channel) ===
def read_digital_inputs():
    # Membaca 4 input mulai dari address 0x0000
    value = instrument.read_bits(0, 4, functioncode=2)
    return value  # list [DI1, DI2, DI3, DI4]


# === Menulis Digital Output (single channel) ===
def write_digital_output(channel, state):
    """
    channel: 0-3 (DO1-DO4)
    state: True=ON, False=OFF
    """
    instrument.write_bit(channel, int(state), functioncode=5)


# === Membaca Digital Output (status 4 channel) ===
def read_digital_outputs():
    value = instrument.read_bits(0, 4, functioncode=1)
    return value  # list [DO1, DO2, DO3, DO4]


if __name__ == "__main__":
    print("Membaca analog input...")
    print(read_analog_channels())  # hasil dalam mA

    print("Membaca digital input...")
    print(read_digital_inputs())

    print("Set DO1=ON")
    write_digital_output(0, True)

    print("Status digital output:")
    print(read_digital_outputs())
