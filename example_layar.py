from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import ili9488
from PIL import Image, ImageDraw, ImageFont
import time
import random
import math

# Inisialisasi perangkat
serial = spi(port=0, device=0, gpio_DC=23, gpio_RST=24)
device = ili9488(serial, rotate=2, gpio_LIGHT=18, active_low=False)
device.backlight(True)

# Font untuk tampilan - ukuran lebih kecil untuk layar 480x320
font_title = ImageFont.truetype(
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 26
)
font_label = ImageFont.truetype(
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20
)
font_value = ImageFont.truetype(
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 24
)
font_unit = ImageFont.truetype(
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18
)
font_page = ImageFont.truetype(
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20
)
font_time = ImageFont.truetype(
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18
)
font_countdown = ImageFont.truetype(
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 16
)

# Warna untuk tema
BG_COLOR = (15, 25, 35)  # Dark blue
HEADER_COLOR = (0, 90, 130)  # Deep blue
PANEL_COLOR = (35, 70, 100)  # Medium blue
TEXT_COLOR = (230, 230, 230)  # Light gray
HIGHLIGHT_COLOR = (0, 200, 255)  # Bright blue
WARNING_COLOR = (255, 90, 90)  # Red for warnings
ACCENT_COLOR = (0, 180, 180)  # Teal accent

# Daftar sensor dan nilai awal
sensors = [
    {
        "name": "pH",
        "value": 7.0,
        "unit": "",
        "min": 0,
        "max": 14,
        "warn_min": 6.5,
        "warn_max": 8.5,
    },
    {
        "name": "TDS",
        "value": 500,
        "unit": "ppm",
        "min": 0,
        "max": 1000,
        "warn_min": 300,
        "warn_max": 700,
    },
    {
        "name": "TSS",
        "value": 100,
        "unit": "mg/L",
        "min": 0,
        "max": 500,
        "warn_min": 50,
        "warn_max": 200,
    },
    {
        "name": "Water Level",
        "value": 75,
        "unit": "%",
        "min": 0,
        "max": 100,
        "warn_min": 20,
        "warn_max": 90,
    },
    {
        "name": "Flow Meter",
        "value": 10.5,
        "unit": "L/min",
        "min": 0,
        "max": 20,
        "warn_min": 5,
        "warn_max": 15,
    },
    {
        "name": "Velocity",
        "value": 2.5,
        "unit": "m/s",
        "min": 0,
        "max": 5,
        "warn_min": 1,
        "warn_max": 4,
    },
    {
        "name": "Debit",
        "value": 150,
        "unit": "m³/h",
        "min": 0,
        "max": 300,
        "warn_min": 100,
        "warn_max": 200,
    },
    {
        "name": "Temperature",
        "value": 150,
        "unit": "m³/h",
        "min": 0,
        "max": 300,
        "warn_min": 100,
        "warn_max": 200,
    },
    {
        "name": "Solar Radiation",
        "value": 150,
        "unit": "m³/h",
        "min": 0,
        "max": 300,
        "warn_min": 100,
        "warn_max": 200,
    },
    {
        "name": "Wind Speed",
        "value": 150,
        "unit": "m³/h",
        "min": 0,
        "max": 300,
        "warn_min": 100,
        "warn_max": 200,
    },
]


# Fungsi untuk menggambar panel dengan sudut membulat (versi lebih efisien)
def draw_rounded_panel(draw, x, y, width, height, radius, color):
    # Gambar bagian utama
    draw.rectangle((x + radius, y, x + width - radius, y + height), fill=color)
    draw.rectangle((x, y + radius, x + width, y + height - radius), fill=color)

    # Gambar sudut membulat
    draw.pieslice([x, y, x + 2 * radius, y + 2 * radius], 180, 270, fill=color)
    draw.pieslice(
        [x + width - 2 * radius, y, x + width, y + 2 * radius], 270, 360, fill=color
    )
    draw.pieslice(
        [x, y + height - 2 * radius, x + 2 * radius, y + height], 90, 180, fill=color
    )
    draw.pieslice(
        [x + width - 2 * radius, y + height - 2 * radius, x + width, y + height],
        0,
        90,
        fill=color,
    )


# Fungsi untuk memperbarui nilai sensor secara acak (simulasi)
def update_sensor_values():
    for sensor in sensors:
        if sensor["name"] == "pH":
            sensor["value"] = round(random.uniform(6.0, 9.0), 1)
        elif sensor["name"] == "TDS":
            sensor["value"] = random.randint(200, 900)
        elif sensor["name"] == "TSS":
            sensor["value"] = random.randint(30, 250)
        elif sensor["name"] == "Water Level":
            sensor["value"] = random.randint(10, 95)
        elif sensor["name"] == "Flow Meter":
            sensor["value"] = round(random.uniform(3.0, 18.0), 1)
        elif sensor["name"] == "Velocity":
            sensor["value"] = round(random.uniform(0.5, 4.5), 1)
        elif sensor["name"] == "Debit":
            sensor["value"] = random.randint(80, 250)


# Fungsi untuk menentukan warna nilai berdasarkan kondisi
def get_value_color(sensor):
    if sensor["value"] < sensor["warn_min"] or sensor["value"] > sensor["warn_max"]:
        return WARNING_COLOR
    return HIGHLIGHT_COLOR


# Fungsi untuk menampilkan halaman sensor
def display_sensor_page(page_number, time_left):
    with canvas(device) as draw:
        # Background gradient (dioptimalkan untuk kinerja)
        draw.rectangle(device.bounding_box, fill=BG_COLOR)

        # Header yang lebih ramping
        header_height = 50
        draw.rectangle((0, 0, 480, header_height), fill=HEADER_COLOR)

        # Judul dengan font lebih kecil
        title = "SENSOR MONITOR"
        title_width = draw.textlength(title, font=font_title)
        draw.text(
            (480 // 2 - title_width // 2, 25), title, font=font_title, fill=TEXT_COLOR
        )

        # Tentukan sensor yang akan ditampilkan (6 sensor per halaman)
        start_index = page_number * 6
        end_index = min(start_index + 6, len(sensors))
        page_sensors = sensors[start_index:end_index]

        # Layout dinamis berdasarkan jumlah sensor
        num_sensors = len(page_sensors)
        panel_height = 0
        panel_spacing = 5  # Jarak antar panel

        if num_sensors == 1:
            # Layout untuk satu sensor (lebih kompak)
            x = 20
            y = 60
            panel_width = 440
            panel_height = 200
            draw_rounded_panel(draw, x, y, panel_width, panel_height, 10, PANEL_COLOR)

            # Tampilkan nama sensor
            draw.text(
                (x + 20, y + 20),
                page_sensors[0]["name"],
                font=font_label,
                fill=TEXT_COLOR,
            )

            # Tampilkan nilai sensor
            value_color = get_value_color(page_sensors[0])
            value_text = f"{page_sensors[0]['value']} {page_sensors[0]['unit']}"
            value_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 36
            )
            value_width = draw.textlength(value_text, font=value_font)
            draw.text(
                (x + panel_width // 2 - value_width // 2, y + 70),
                value_text,
                font=value_font,
                fill=value_color,
            )

            # Tampilkan indikator rentang
            min_text = f"Min: {page_sensors[0]['warn_min']}"
            max_text = f"Max: {page_sensors[0]['warn_max']}"
            draw.text((x + 30, y + 140), min_text, font=font_label, fill=TEXT_COLOR)
            draw.text(
                (
                    x + panel_width - 30 - draw.textlength(max_text, font=font_label),
                    y + 140,
                ),
                max_text,
                font=font_label,
                fill=TEXT_COLOR,
            )

        else:
            # Layout grid 3x2 untuk 2-6 sensor
            cols = 2
            rows = 3
            panel_width = 220
            panel_height = 75

            for i, sensor in enumerate(page_sensors):
                row = i // cols
                col = i % cols

                x = 20 + col * (panel_width + panel_spacing)
                y = 60 + row * (panel_height + panel_spacing)

                # Pastikan panel tidak keluar batas layar
                if y + panel_height > 310:
                    continue

                draw_rounded_panel(
                    draw, x, y, panel_width, panel_height, 8, PANEL_COLOR
                )

                # Tampilkan nama sensor
                name_text = sensor["name"]
                if draw.textlength(name_text, font=font_label) > 140:
                    name_text = (
                        name_text[:12] + "..." if len(name_text) > 12 else name_text
                    )
                draw.text((x + 10, y + 10), name_text, font=font_label, fill=TEXT_COLOR)

                # Tampilkan nilai sensor
                value_color = get_value_color(sensor)
                value_text = f"{sensor['value']}"
                value_width = draw.textlength(value_text, font=font_value)
                draw.text(
                    (x + panel_width - value_width - 10, y + 10),
                    value_text,
                    font=font_value,
                    fill=value_color,
                )

                # Tampilkan satuan
                draw.text(
                    (
                        x
                        + panel_width
                        - draw.textlength(sensor["unit"], font=font_unit)
                        - 10,
                        y + 40,
                    ),
                    sensor["unit"],
                    font=font_unit,
                    fill=(180, 180, 200),
                )

                # Tampilkan indikator status
                status = "OK"
                if sensor["value"] < sensor["warn_min"]:
                    status = "LOW"
                elif sensor["value"] > sensor["warn_max"]:
                    status = "HIGH"

                status_color = HIGHLIGHT_COLOR if status == "OK" else WARNING_COLOR
                status_width = draw.textlength(status, font=font_unit)
                draw.text((x + 10, y + 40), status, font=font_unit, fill=status_color)

        # Footer dengan informasi halaman
        footer_height = 30
        footer_y = 320 - footer_height
        draw.rectangle((0, footer_y, 480, 320), fill=HEADER_COLOR)

        total_pages = (len(sensors) + 5) // 6
        page_text = f"Page {page_number + 1}/{total_pages}"
        page_width = draw.textlength(page_text, font=font_page)
        draw.text(
            (20, footer_y + footer_height // 2),
            page_text,
            font=font_page,
            fill=TEXT_COLOR,
            anchor="lm",
        )

        # Tampilkan waktu saat ini
        time_text = time.strftime("%H:%M:%S")
        time_width = draw.textlength(time_text, font=font_time)
        draw.text(
            (480 - 20, footer_y + footer_height // 2),
            time_text,
            font=font_time,
            fill=TEXT_COLOR,
            anchor="rm",
        )

        # Indikator status sistem
        status_color = HIGHLIGHT_COLOR
        for sensor in sensors:
            if (
                sensor["value"] < sensor["warn_min"]
                or sensor["value"] > sensor["warn_max"]
            ):
                status_color = WARNING_COLOR
                break
        draw.ellipse(
            (480 // 2 - 15, footer_y + 7, 480 // 2 + 15, footer_y + 23),
            fill=status_color,
        )

        # Tampilkan countdown pergantian halaman
        countdown_text = f"Next: {time_left}s"
        countdown_width = draw.textlength(countdown_text, font=font_countdown)
        draw.text(
            (480 // 2 - countdown_width // 2, footer_y + footer_height // 2),
            countdown_text,
            font=font_countdown,
            fill=(200, 200, 100),
            anchor="lm",
        )


# Main loop
try:
    page_count = (len(sensors) + 5) // 6  # Hitung jumlah halaman
    current_page = 0

    # Tampilkan halaman pertama
    last_update = time.time()
    last_change = time.time()

    while True:
        now = time.time()
        time_left = 20 - int(now - last_change)
        if time_left < 0:
            time_left = 0

        # Perbarui nilai sensor setiap 2 detik
        if now - last_update >= 2:
            update_sensor_values()
            last_update = now

        # Tampilkan halaman saat ini dengan waktu countdown
        display_sensor_page(current_page, time_left)

        # Ganti halaman setiap 20 detik
        if now - last_change >= 20:
            last_change = now
            current_page = (current_page + 1) % page_count

        # Untuk layar yang responsif
        time.sleep(0.1)

except KeyboardInterrupt:
    device.backlight(False)
    device.cleanup()
