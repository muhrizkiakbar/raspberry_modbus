import serial
import crcmod
import time

# Konfigurasi Port Serial
ser = serial.Serial("/dev/ttyUSB0", 9600, bytesize=8, parity="N", stopbits=1, timeout=1)

# Fungsi CRC16 Modbus
crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)

# --------------------------------------------
# 1. KONFIGURASI MODUL KE RENTANG 4-20mA
# --------------------------------------------
# Register 40625 (0x0064) untuk set rentang input
# 0x0000 = 0-20mA (default), 0x0001 = 4-20mA

# Bangun frame untuk set 4-20mA
write_frame = bytes(
    [
        0x01,  # Slave address
        0x06,  # Function code (Write Single Register)
        0x00,
        0x64,  # Register address (0x0064 = 40625)
        0x00,
        0x01,  # Value to write (0x0001 = 4-20mA)
    ]
)

# Hitung CRC dan tambahkan ke frame
write_crc = crc16(write_frame).to_bytes(2, "little")
write_frame += write_crc

# Kirim perintah konfigurasi
ser.write(write_frame)
time.sleep(0.5)  # Beri waktu untuk modul memproses

# Baca respons konfigurasi
write_response = ser.read(8)
print("\nKonfigurasi 4-20mA Response:", write_response.hex())

# --------------------------------------------
# 2. BACA DATA SENSOR TDS DARI AI_1+
# --------------------------------------------
# Kirim permintaan baca 6 register mulai dari 0x0000
ser.write(b"\x01\x03\x00\x00\x00\x06\xc5\xc8")
time.sleep(0.1)

# Baca respons
read_response = ser.read(17)
print("\nRaw response:", read_response.hex())

# Parsing data
if len(read_response) >= 15:
    # Verifikasi CRC
    received_crc = int.from_bytes(read_response[-2:], "little")
    calculated_crc = crc16(read_response[:-2])

    if received_crc == calculated_crc:
        data_bytes = read_response[3:-2]
        registers = [
            int.from_bytes(data_bytes[i : i + 2], byteorder="big")
            for i in range(0, len(data_bytes), 2)
        ]
        print("\nRegister values:", registers)

        # Konversi ke mA dan TDS (AI_1+ saja)
        raw_ai1 = registers[0]
        current = (raw_ai1 * 20) / 4095

        # Jika rentang 4-20mA
        if current >= 4:
            tds = (current - 4) * (1000 / 16)  # Contoh: 4-20mA → 0-1000 ppm
            print(f"Arus AI_1+: {current:.2f} mA")
            print(f"TDS: {tds:.2f} ppm")
        else:
            print("Sensor error: Arus < 4mA")
    else:
        print("CRC Error!")
else:
    print("Response tidak valid")

ser.close()
