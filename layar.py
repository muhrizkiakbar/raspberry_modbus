from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import ili9488
from PIL import ImageFont
import time
import random

# Inisialisasi perangkat
serial = spi(port=0, device=0, gpio_DC=23, gpio_RST=24)
device = ili9488(serial, rotate=2, gpio_LIGHT=18, active_low=False) 
device.backlight(True)

# Font untuk tampilan
font_label = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 24)
font_value = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 28)

# Daftar sensor dan nilai awal
sensors = [
    {"name": "pH", "value": 7.0, "unit": "", "color": "cyan"},
    {"name": "TDS", "value": 500, "unit": "ppm", "color": "yellow"},
    {"name": "TSS", "value": 100, "unit": "mg/L", "color": "magenta"},
    {"name": "Water Level", "value": 75, "unit": "%", "color": "blue"},
    {"name": "Flow Meter", "value": 10.5, "unit": "L/min", "color": "green"},
    {"name": "Velocity", "value": 2.5, "unit": "m/s", "color": "red"},
    {"name": "Debit", "value": 150, "unit": "m³/h", "color": "orange"},
]

# Fungsi untuk memperbarui nilai sensor secara acak (simulasi)
def update_sensor_values():
    for sensor in sensors:
        if sensor["name"] == "pH":
            sensor["value"] = round(random.uniform(6.5, 8.5), 1)
        elif sensor["name"] == "TDS":
            sensor["value"] = random.randint(300, 800)
        elif sensor["name"] == "TSS":
            sensor["value"] = random.randint(50, 200)
        elif sensor["name"] == "Water Level":
            sensor["value"] = random.randint(60, 100)
        elif sensor["name"] == "Flow Meter":
            sensor["value"] = round(random.uniform(5.0, 15.0), 1)
        elif sensor["name"] == "Velocity":
            sensor["value"] = round(random.uniform(1.0, 4.0), 1)
        elif sensor["name"] == "Debit":
            sensor["value"] = random.randint(100, 200)

# Fungsi untuk menampilkan halaman sensor
def display_sensor_page(page_number):
    with canvas(device) as draw:
        # Bersihkan layar
        draw.rectangle(device.bounding_box, fill="black")
        
        # Tampilkan header
        draw.text((10, 5), f"Sensor Page {page_number+1}", font=font_label, fill="white")
        draw.line((10, 35, 470, 35), fill="white", width=2)
        
        # Tentukan sensor yang akan ditampilkan (6 sensor per halaman)
        start_index = page_number * 6
        end_index = min(start_index + 6, len(sensors))
        page_sensors = sensors[start_index:end_index]
        
        # Jika sensor di halaman terakhir kurang dari 6, tambahkan dari awal
        if len(page_sensors) < 6:
            needed = 6 - len(page_sensors)
            page_sensors += sensors[0:needed]
        
        # Tampilkan sensor
        y_position = 45
        for sensor in page_sensors:
            # Tampilkan label sensor
            label = f"{sensor['name']}:"
            draw.text((20, y_position), label, font=font_label, fill="white")
            
            # Tampilkan nilai dan satuan
            value_text = f"{sensor['value']} {sensor['unit']}"
            value_width = draw.textlength(value_text, font=font_value)
            draw.text((480 - value_width - 20, y_position), value_text, font=font_value, fill=sensor['color'])
            
            y_position += 40

# Main loop
try:
    page_count = (len(sensors) + 5) // 6  # Hitung jumlah halaman
    current_page = 0
    
    while True:
        # Perbarui nilai sensor
        update_sensor_values()
        
        # Tampilkan halaman saat ini
        display_sensor_page(current_page)
        
        # Pindah ke halaman berikutnya
        current_page = (current_page + 1) % page_count
        
        # Tunggu 5 detik sebelum berganti halaman
        time.sleep(5)

except KeyboardInterrupt:
    device.backlight(False)
    device.cleanup()
