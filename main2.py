import serial
import crcmod
import time

# Konfigurasi Port Serial (Sesuaikan dengan Port Anda!)
ser = serial.Serial(
    port="/dev/ttyUSB0",  # Ganti ke COMx di Windows
    baudrate=9600,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=1,
)

# Fungsi CRC16 Modbus RTU
crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)


def read_analog_channel(slave_address, channel_address):
    # Bangun frame MODBUS (Function Code 0x03)
    frame = bytes(
        [
            slave_address,
            0x03,  # Function code: Read Holding Registers
            (channel_address >> 8) & 0xFF,  # High byte alamat register
            channel_address & 0xFF,  # Low byte alamat register
            0x00,  # High byte jumlah register
            0x01,  # Low byte jumlah register (baca 1 register)
        ]
    )
    # Hitung CRC dan tambahkan ke frame
    crc = crc16(frame).to_bytes(2, "little")
    return frame + crc


# Parameter untuk AI_1+ (Register 40001)
SLAVE_ADDRESS = 0x01
CHANNEL_ADDRESS = 0x0000  # Alamat MODBUS 40001 = 0x0000

try:
    while True:
        # Kirim perintah baca AI_1+
        request = read_analog_channel(SLAVE_ADDRESS, CHANNEL_ADDRESS)
        ser.write(request)

        # Baca respons (7 byte: 1+1+1+2+2)
        response = ser.read(7)

        if len(response) == 7:
            # Verifikasi CRC
            received_crc = int.from_bytes(response[-2:], "little")
            calculated_crc = crc16(response[:-2])

            if received_crc == calculated_crc:
                # Ekstrak nilai raw (2 byte setelah header)
                raw_value = int.from_bytes(response[3:5], "big")

                # Konversi ke mA (4-20mA)
                current = (raw_value * 20) / 4095
                print(f"Arus AI_1+: {current:.2f} mA")

                # Konversi ke TDS (contoh: 4-20mA → 0-1000 ppm)
                if current >= 4:
                    # tds = (current - 4) * (1000 / 16)
                    tds = (current - 4) * (14 / 16)
                    print(f"PH: {tds:.2f}")
                    # print(f"PH: {tds:.2f} ppm")
                else:
                    print("ERROR: Arus < 4mA (Sensor tidak aktif)")
            else:
                print("ERROR: CRC tidak valid!")
        else:
            print("ERROR: Respons tidak lengkap!")

        time.sleep(2)

except KeyboardInterrupt:
    ser.close()
    print("\nPort ditutup")

except Exception as e:
    print(f"ERROR: {str(e)}")
    ser.close()
