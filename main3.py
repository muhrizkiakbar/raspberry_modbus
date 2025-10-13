import serial
import crcmod
import time
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import Adafruit_SSD1306
from PIL import Image, ImageDraw, ImageFont

# ==============================
# Konfigurasi Port Serial
# ==============================
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

# ==============================
# Konfigurasi OLED
# ==============================
OLED_WIDTH = 128
OLED_HEIGHT = 64
oled = Adafruit_SSD1306.SSD1306_128_64(rst=None)
oled.begin()
oled.clear()
oled.display()

# Font
font_path = "/home/pi/raspberry_modbus/fonts/Tahoma.ttf"
font = ImageFont.truetype(font_path, 15)


def display_message(line1, top_margin=8, bottom_margin=8):
    try:
        image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)

        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            current_line = []
            current_width = 0
            space_width = font.getlength(" ")

            for word in words:
                word_width = font.getlength(word)
                if word_width > max_width:
                    for char in word:
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

        all_lines = []
        for original_line in line1.split("\n"):
            wrapped_lines = wrap_text(original_line, font, OLED_WIDTH)
            all_lines.extend(wrapped_lines)

        bbox = font.getbbox("A")
        char_height = bbox[3] - bbox[1]
        total_text_height = len(all_lines) * char_height
        y_offset = top_margin

        for line_text in all_lines:
            text_width = font.getlength(line_text)
            x_offset = max(0, (OLED_WIDTH - text_width) // 2)

            if y_offset + char_height > OLED_HEIGHT - bottom_margin:
                break

            draw.text((x_offset, y_offset), line_text, font=font, fill=255)
            y_offset += char_height

        image = image.rotate(180)
        oled.image(image)
        oled.display()
    except Exception as e:
        print(f"OLED Display Error: {e}")


# ==============================
# Fungsi Baca Modbus
# ==============================
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


# ==============================
# Konfigurasi MQTT
# ==============================
MQTT_BROKER = "eqmx.telemetry-adaro.id"
MQTT_PORT = 1883
MQTT_BASE_TOPIC = "kebun"
MQTT_COMMAND_TOPIC = "kebun/perintah"
MQTT_QOS = 1
MQTT_CLIENT_ID = "kebun"
MQTT_USERNAME = "griyasokaponik"
MQTT_PASSWORD = "griyasokaponik"

client = mqtt.Client(client_id=MQTT_CLIENT_ID)
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ MQTT Connected")
        client.subscribe(MQTT_COMMAND_TOPIC, qos=MQTT_QOS)
    else:
        print(f"❌ MQTT Failed to connect, code: {rc}")


def on_message(client, userdata, msg):
    print(f"📩 Command received on {msg.topic}: {msg.payload.decode()}")


client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# ==============================
# Main Loop
# ==============================
SLAVE_ADDRESS = 0x01
CHANNEL_COUNT = 2
mqtt_timer = time.time()

try:
    oled_text = ""
    while True:
        data = {}
        for i in range(CHANNEL_COUNT):
            channel_address = 0x0000 + i
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
                            ph = (current - 4) * (14 / 16)
                            data["ph"] = round(ph, 2)
                            oled_text = f"PH: {ph:.2f}"
                            print(f"→ PH: {ph:.2f}")
                        else:
                            print("→ Sensor tidak aktif (<4mA)")
                    elif (i + 1) == 2:
                        if current >= 4:
                            tds = (current - 4) * (2000 / 16)
                            data["tds"] = round(tds, 2)
                            oled_text += f"\n -- \n TDS: {tds:.2f}"
                            print(f"→ TDS: {tds:.2f} PPm")
                        else:
                            print("→ Sensor tidak aktif (<4mA)")
                    else:
                        print("Analog tidak ditemukan")
                else:
                    print(f"[AI_{i + 1}] ERROR: CRC tidak valid!")
            else:
                print(f"[AI_{i + 1}] ERROR: Respons tidak lengkap!")

            time.sleep(0.2)

        display_message(oled_text)

        # ==============================
        # Pengiriman ke MQTT tiap 15 menit
        # ==============================
        if time.time() - mqtt_timer >= 900:  # 900 detik = 15 menit
            payload = {
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            client.publish(MQTT_BASE_TOPIC, json.dumps(payload), qos=MQTT_QOS)
            print(f"📤 MQTT Publish → {MQTT_BASE_TOPIC}: {payload}")
            mqtt_timer = time.time()

        time.sleep(2)

except KeyboardInterrupt:
    ser.close()
    client.loop_stop()
    client.disconnect()
    print("\n🔌 Port serial & MQTT ditutup")

except Exception as e:
    print(f"ERROR: {str(e)}")
    ser.close()
    client.loop_stop()
    client.disconnect()
