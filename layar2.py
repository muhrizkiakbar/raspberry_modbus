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

# Font untuk tampilan
font_title = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 32)
font_label = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 22)
font_value = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 26)
font_unit = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18)
font_page = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20)

# Warna untuk tema
BG_COLOR = (10, 20, 30)  # Dark blue
HEADER_COLOR = (0, 80, 120)  # Deep blue
PANEL_COLOR = (30, 60, 90)  # Medium blue
TEXT_COLOR = (220, 220, 220)  # Light gray
HIGHLIGHT_COLOR = (0, 180, 255)  # Bright blue
WARNING_COLOR = (255, 100, 100)  # Red for warnings

# Daftar sensor dan nilai awal
sensors = [
    {"name": "pH", "value": 7.0, "unit": "", "icon": "🧪", "min": 0, "max": 14, "warn_min": 6.5, "warn_max": 8.5},
    {"name": "TDS", "value": 500, "unit": "ppm", "icon": "🧂", "min": 0, "max": 1000, "warn_min": 300, "warn_max": 700},
    {"name": "TSS", "value": 100, "unit": "mg/L", "icon": "💧", "min": 0, "max": 500, "warn_min": 50, "warn_max": 200},
    {"name": "Water Level", "value": 75, "unit": "%", "icon": "📊", "min": 0, "max": 100, "warn_min": 20, "warn_max": 90},
    {"name": "Flow Meter", "value": 10.5, "unit": "L/min", "icon": "🌊", "min": 0, "max": 20, "warn_min": 5, "warn_max": 15},
    {"name": "Velocity", "value": 2.5, "unit": "m/s", "icon": "🚀", "min": 0, "max": 5, "warn_min": 1, "warn_max": 4},
    {"name": "Debit", "value": 150, "unit": "m³/h", "icon": "⏱️", "min": 0, "max": 300, "warn_min": 100, "warn_max": 200},
]

# Fungsi untuk menggambar panel dengan sudut membulat
def draw_rounded_panel(draw, x, y, width, height, radius, color):
    # Draw main rectangle
    draw.rectangle((x + radius, y, x + width - radius, y + height), fill=color)
    draw.rectangle((x, y + radius, x + width, y + height - radius), fill=color)
    
    # Draw rounded corners
    draw.pieslice([x, y, x + 2*radius, y + 2*radius], 180, 270, fill=color)
    draw.pieslice([x + width - 2*radius, y, x + width, y + 2*radius], 270, 360, fill=color)
    draw.pieslice([x, y + height - 2*radius, x + 2*radius, y + height], 90, 180, fill=color)
    draw.pieslice([x + width - 2*radius, y + height - 2*radius, x + width, y + height], 0, 90, fill=color)

# Fungsi untuk menggambar progress bar
def draw_progress_bar(draw, x, y, width, height, value, min_val, max_val, color):
    # Draw background
    draw.rectangle((x, y, x + width, y + height), fill=(40, 40, 60))
    
    # Calculate progress width
    progress_width = int(width * (value - min_val) / (max_val - min_val))
    if progress_width < 0:
        progress_width = 0
    elif progress_width > width:
        progress_width = width
    
    # Draw progress
    draw.rectangle((x, y, x + progress_width, y + height), fill=color)
    
    # Draw border
    draw.rectangle((x, y, x + width, y + height), outline=(100, 100, 120), width=1)

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
def display_sensor_page(page_number, animation_progress=100):
    with canvas(device) as draw:
        # Background gradient
        for i in range(320):
            r = BG_COLOR[0] + int(i/320*20)
            g = BG_COLOR[1] + int(i/320*15)
            b = BG_COLOR[2] + int(i/320*25)
            draw.line((0, i, 480, i), fill=(r, g, b))
        
        # Header dengan sudut membulat
        draw_rounded_panel(draw, 10, 10, 460, 60, 15, HEADER_COLOR)
        
        # Judul dengan efek bayangan
        draw.text((242, 37), "SENSOR MONITOR", font=font_title, fill=(0, 0, 30), anchor="mm")
        draw.text((240, 35), "SENSOR MONITOR", font=font_title, fill=TEXT_COLOR, anchor="mm")
        
        # Tentukan sensor yang akan ditampilkan (6 sensor per halaman)
        start_index = page_number * 6
        end_index = min(start_index + 6, len(sensors))
        page_sensors = sensors[start_index:end_index]
        
        # Jika sensor di halaman terakhir kurang dari 6, tambahkan dari awal
        if len(page_sensors) < 6:
            needed = 6 - len(page_sensors)
            page_sensors += sensors[0:needed]
        
        # Animasi transisi
        offset_x = int((100 - animation_progress) * 4.8)
        
        # Tampilkan sensor
        for i, sensor in enumerate(page_sensors):
            row = i % 3
            col = i // 3
            
            x = 20 + col * 230 + offset_x
            y = 90 + row * 70
            
            # Gambar panel sensor dengan sudut membulat
            panel_color = PANEL_COLOR
            if sensor["value"] < sensor["warn_min"] or sensor["value"] > sensor["warn_max"]:
                panel_color = (80, 30, 30)  # Warna peringatan
            
            draw_rounded_panel(draw, x, y, 210, 60, 10, panel_color)
            
            # Tampilkan ikon sensor
            icon_size = draw.textbbox((0, 0), sensor["icon"], font=font_label)
            icon_width = icon_size[2] - icon_size[0]
            draw.text((x + 20, y + 30), sensor["icon"], font=font_label, fill=TEXT_COLOR, anchor="lm")
            
            # Tampilkan nama sensor
            draw.text((x + 50, y + 15), sensor["name"], font=font_label, fill=TEXT_COLOR)
            
            # Tampilkan nilai sensor
            value_text = f"{sensor['value']}"
            value_color = get_value_color(sensor)
            draw.text((x + 50, y + 40), value_text, font=font_value, fill=value_color)
            
            # Tampilkan satuan
            draw.text((x + 50 + draw.textlength(value_text, font=font_value) + 5, y + 45), 
                     sensor["unit"], font=font_unit, fill=(180, 180, 200))
            
            # Tampilkan progress bar
            progress_height = 8
            progress_y = y + 55
            draw_progress_bar(draw, x + 130, progress_y, 70, progress_height, 
                             sensor["value"], sensor["min"], sensor["max"], value_color)
        
        # Footer dengan informasi halaman
        total_pages = (len(sensors) + 5) // 6
        page_text = f"Page {page_number+1} of {total_pages}"
        page_width = draw.textlength(page_text, font=font_page)
        
        draw_rounded_panel(draw, 480//2 - page_width//2 - 15, 280, page_width + 30, 30, 15, HEADER_COLOR)
        draw.text((480//2, 295), page_text, font=font_page, fill=TEXT_COLOR, anchor="mm")
        
        # Tampilkan waktu saat ini
        time_text = time.strftime("%H:%M:%S")
        draw.text((480 - 20, 295), time_text, font=font_unit, fill=(150, 150, 170), anchor="rm")

# Fungsi animasi transisi
def animate_page_transition(current_page, next_page):
    for progress in range(0, 101, 10):  # 10 langkah animasi
        display_sensor_page(current_page, progress)
        time.sleep(0.02)
    
    for progress in range(0, 101, 10):  # 10 langkah animasi
        display_sensor_page(next_page, 100 - progress)
        time.sleep(0.02)
    
    display_sensor_page(next_page)

# Main loop
try:
    page_count = (len(sensors) + 5) // 6  # Hitung jumlah halaman
    current_page = 0
    
    # Tampilkan halaman pertama
    display_sensor_page(current_page)
    
    last_update = time.time()
    last_change = time.time()
    
    while True:
        now = time.time()
        
        # Perbarui nilai sensor setiap 2 detik
        if now - last_update >= 2:
            update_sensor_values()
            last_update = now
            display_sensor_page(current_page)
        
        # Ganti halaman setiap 8 detik
        if now - last_change >= 8:
            last_change = now
            next_page = (current_page + 1) % page_count
            
            # Gunakan animasi transisi
            animate_page_transition(current_page, next_page)
            current_page = next_page
        else:
            # Untuk layar yang responsif
            time.sleep(0.1)

except KeyboardInterrupt:
    device.backlight(False)
    device.cleanup()
