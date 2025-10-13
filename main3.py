import serial
import crcmod
import time
import Adafruit_SSD1306
from PIL import Image, ImageDraw, ImageFont
import textwrap
import paho.mqtt.client as mqtt
import json

# ========== KONFIGURASI SERIAL ==========
ser = serial.Serial(
    port="/dev/ttyUSB0",
    baudrate=9600,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=1,
)

# ========== KONFIGURASI CRC ==========
crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)

# ========== KONFIGURASI OLED ==========
OLED_WIDTH = 128
OLED_HEIGHT = 64
oled = Adafruit_SSD1306.SSD1306_128_64(rst=None)
oled.begin()
oled.clear()
oled.display()

font_path = "/home/pi/raspberry_modbus/fonts/Tahoma.ttf"
font = ImageFont.truetype(font_path, 15)

# ========== KONFIGURASI MQTT ==========
MQTT_BROKER = "eqmx.telemetry-adaro.id"
MQTT_PORT = 1883
MQTT_BASE_TOPIC = "kebun"
MQTT_COMMAND_TOPIC = "kebun/perintah"
MQTT_CLIENT_ID = "kebun"
MQTT_USERNAME = "griyasokaponik"
MQTT_PASSWORD = "griyasokaponik"
MQTT_QOS = 1

client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Terhubung ke broker ✅")
        client.subscribe(MQTT_COMMAND_TOPIC, qos=MQTT_QOS)
    else:
        print(f"[MQTT] Gagal terhubung, kode: {rc}")


def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Terputus dari broker (kode {rc}), mencoba ulang...")
    reconnect_mqtt()


def on_message(client, userdata, msg):
    pesan = msg.payload.decode()
    print(f"[MQTT] Pesan diterima di {msg.topic}: {pesan}")
    # Jika ingin menampilkan perintah ke OLED:
    display_message(f"CMD:\n{pesan}")


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message


def reconnect_mqtt():
    while True:
        try:
            print("[MQTT] Mencoba koneksi ulang...")
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_start()
            break
        except Exception as e:
            print(f"[MQTT] Gagal koneksi ulang: {e}")
            time.sleep(5)


def connect_mqtt():
    while True:
        try:
            print("[MQTT] Menghubungkan ke broker...")
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_start()
            break
        except Exception as e:
            print(f"[MQTT] Gagal koneksi: {e}, mencoba ulang dalam 5 detik...")
            time.sleep(5)


connect_mqtt()


# ========== FUNGSI OLED ==========
def display_message(line1, top_margin=8, bottom_margin=8):
    try:
        image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)

        def wrap_text(text, font, max_width):
            words = text.split()
            lines, current_line, current_width = [], [], 0
            space_width = font.getlength(" ")
            for word in words:
                word_width = font.getlength(word)
                if word_width > max_width:
                    for char in list(word):
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
                new_width = (
                    (current_width + space_width + word_width)
                    if current_line
                    else word_width
                )
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
            all_lines.extend(wrap_text(original_line, font, OLED_WIDTH))

        bbox = font.getbbox("A")
        char_height = bbox[3] - bbox[1]
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


# ========== FUNGSI MODBUS ==========
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


# ========== LOOP UTAMA ==========
SLAVE_ADDRESS = 0x01
CHANNEL_COUNT = 2

try:
    oled_text = ""
    while True:
        data_payload = {}
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

                    if (i + 1) == 1 and current >= 4:
                        ph = (current - 4) * (14 / 16)
                        oled_text = f"PH: {ph:.2f}"
                        data_payload["ph"] = round(ph, 2)
                        print(f"→ PH: {ph:.2f}")
                    elif (i + 1) == 2 and current >= 4:
                        tds = (current - 4) * (2000 / 16)
                        oled_text += f"\n -- \nTDS: {tds:.2f}"
                        data_payload["tds"] = round(tds, 2)
                        print(f"→ TDS: {tds:.2f} PPM")
                    else:
                        print("→ Sensor tidak aktif (<4mA)")
                else:
                    print(f"[AI_{i + 1}] ERROR: CRC tidak valid!")
            else:
                print(f"[AI_{i + 1}] ERROR: Respons tidak lengkap!")

            time.sleep(0.2)

        display_message(oled_text)

        # Kirim data ke MQTT
        if data_payload:
            mqtt_topic = f"{MQTT_BASE_TOPIC}"
            payload_json = json.dumps(data_payload)
            result = client.publish(mqtt_topic, payload_json, qos=MQTT_QOS)
            status = result.rc
            if status == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Data terkirim ke {mqtt_topic}: {payload_json}")
            else:
                print(f"[MQTT] Gagal kirim data: {payload_json}")

        time.sleep(2)

except KeyboardInterrupt:
    ser.close()
    client.loop_stop()
    client.disconnect()
    print("\nPort dan MQTT ditutup")

except Exception as e:
    print(f"ERROR: {str(e)}")
    ser.close()
    client.loop_stop()
    client.disconnect()
