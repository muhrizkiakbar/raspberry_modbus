import serial
import crcmod
import time

# Konfigurasi Port Serial
ser = serial.Serial(
    port="/dev/ttyUSB0",
    baudrate=9600,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=1,
)

# Fungsi CRC16 Modbus RTU
crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)


def read_analog_channel(slave_address, channel_address):
    frame = bytes(
        [
            slave_address,
            0x03,
            (channel_address >> 8) & 0xFF,
            channel_address & 0xFF,
            0x00,
            0x01,
        ]
    )
    crc = crc16(frame).to_bytes(2, "little")
    return frame + crc


SLAVE_ADDRESS = 0x01
CHANNEL_COUNT = 2  # Total 7 channel analog

try:
    while True:
        for i in range(CHANNEL_COUNT):
            channel_address = 0x0000 + i  # Register berturut dari 0x0000, 0x0001, ...
            request = read_analog_channel(SLAVE_ADDRESS, channel_address)
            ser.write(request)

            response = ser.read(7)

            if len(response) == 7:
                received_crc = int.from_bytes(response[-2:], "little")
                calculated_crc = crc16(response[:-2])

                if received_crc == calculated_crc:
                    raw_value = int.from_bytes(response[3:5], "big")
                    current = (raw_value * 20) / 4095
                    print(f"[AI_{i + 1}] Arus: {current:.2f} mA", end=" ")

                    if (i + 1) == 1:
                        if current >= 4:
                            # Contoh konversi TDS / pH / ppm, sesuaikan kebutuhan tiap channel
                            ph = (current - 4) * (14 / 16)
                            print(f"→ PH: {ph:.2f}")
                        else:
                            print("→ Sensor tidak aktif (<4mA)")
                    elif (i + 1) == 2:
                        if current >= 4:
                            # Contoh konversi TDS / pH / ppm, sesuaikan kebutuhan tiap channel
                            # ph = (current - 4) * (2000 / 16)
                            ph = (current - 4) * (2000 / 16)
                            print(f"→ TDS: {ph:.2f} PPm")
                        else:
                            print("→ Sensor tidak aktif (<4mA)")
                    elif (i + 1) == 3:
                        if current >= 4:
                            # Contoh konversi TDS / pH / ppm, sesuaikan kebutuhan tiap channel
                            ph = (current - 4) * (3000 / 16)
                            print(f"→ TSS: {ph:.2f} mg/l")
                        else:
                            print("→ Sensor tidak aktif (<4mA) tss")
                    else:
                        print("Analog tidak ditemukan")

                else:
                    print(f"[AI_{i + 1}] ERROR: CRC tidak valid!")
            else:
                print(f"[AI_{i + 1}] ERROR: Respons tidak lengkap!")

            time.sleep(0.2)  # Delay antar channel untuk stabilitas komunikasi

        time.sleep(2)  # Delay antar siklus pembacaan

except KeyboardInterrupt:
    ser.close()
    print("\nPort ditutup")

except Exception as e:
    print(f"ERROR: {str(e)}")
    ser.close()
