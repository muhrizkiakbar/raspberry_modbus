import serial
import crcmod
import time
import Adafruit_SSD1306
from PIL import Image, ImageDraw, ImageFont
import textwrap

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

OLED_WIDTH = 128
OLED_HEIGHT = 64
oled = Adafruit_SSD1306.SSD1306_128_64(rst=None)

# Font Configuration
font_path = "/home/pi//raspberry_modbus/fonts/Tahoma.ttf"
font = ImageFont.truetype(font_path, 11)


def display_message(line1):
    """Display messages on OLED screen with larger font and newline support"""
    try:
        oled.begin()
        oled.clear()
        image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)

        # Fungsi untuk wrap teks berdasarkan lebar piksel
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            current_line = []
            current_width = 0
            space_width = font.getlength(" ")

            for word in words:
                word_width = font.getlength(word)

                # Penanganan kata yang terlalu panjang
                if word_width > max_width:
                    # Pecah kata menjadi karakter-per-karakter
                    chars = list(word)
                    for char in chars:
                        char_width = font.getlength(char)
                        if (
                            current_line
                            and (current_width + space_width + char_width) <= max_width
                        ):
                            current_line.append(char)
                            current_width += space_width + char_width
                        else:
                            if current_line:
                                lines.append("".join(current_line))
                            current_line = [char]
                            current_width = char_width
                    continue

                # Hitung lebar baru jika menambahkan kata
                if current_line:
                    new_width = current_width + space_width + word_width
                else:
                    new_width = word_width

                if new_width <= max_width:
                    current_line.append(word)
                    current_width = new_width
                else:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_width = word_width

            if current_line:
                lines.append(" ".join(current_line))
            return lines

        # Proses baris baru dan wrap teks
        all_lines = []
        for original_line in line1.split("\n"):
            wrapped_lines = wrap_text(original_line, font, OLED_WIDTH)
            all_lines.extend(wrapped_lines)

        # Hitung dimensi teks
        bbox = font.getbbox("A")  # Dapatkan bounding box
        char_height = bbox[3] - bbox[1]  # Hitung tinggi karakter
        total_text_height = len(all_lines) * char_height

        # Hitung posisi vertikal mulai
        y_offset = max(0, (OLED_HEIGHT - total_text_height) // 2)

        # Gambar setiap baris
        for line_text in all_lines:
            text_width = font.getlength(line_text)
            x_offset = max(0, (OLED_WIDTH - text_width) // 2)
            draw.text((x_offset, y_offset), line_text, font=font, fill=255)
            y_offset += char_height

        oled.image(image)
        oled.display()
    except Exception as e:
        print(f"OLED Display Error: {e}")


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
        oled_text = ""
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

                            oled_text = oled_text + "PH: %s" % (round(ph, 2))
                            print(f"→ PH: {ph:.2f}")
                        else:
                            print("→ Sensor tidak aktif (<4mA)")
                    elif (i + 1) == 2:
                        if current >= 4:
                            # Contoh konversi TDS / pH / ppm, sesuaikan kebutuhan tiap channel
                            # ph = (current - 4) * (2000 / 16)
                            tds = (current - 4) * (2000 / 16)
                            oled_text = oled_text + "\n TDS: %s" % (round(tds, 2))
                            print(f"→ TDS: {tds:.2f} PPm")
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

        display_message(oled_text)
        time.sleep(2)  # Delay antar siklus pembacaan

except KeyboardInterrupt:
    ser.close()
    print("\nPort ditutup")

except Exception as e:
    print(f"ERROR: {str(e)}")
    ser.close()
