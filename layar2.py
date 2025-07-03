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
font_label = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 24)
font_value = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 28)
font_unit = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20)
font_page = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 22)
font_time = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20)
font_countdown = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18)

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

# Fungsi untuk menggambar gauge lingkaran
def draw_gauge(draw, x, y, radius, value, min_val, max_val, color):
    # Lingkaran latar belakang
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), 
                outline=(60, 60, 80), width=2)
    
    # Hitung sudut
    angle = 270 * (value - min_val) / (max_val - min_val)
    
    # Gambar arc
    start_angle = -45
    end_angle = start_angle + angle
    draw.arc((x - radius, y - radius, x + radius, y + radius), 
             start_angle, end_angle, fill=color, width=6)
    
    # Gambar titik pusat
    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color)

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
        # Background gradient
        for i in range(320):
            r = BG_COLOR[0] + int(i/320*20)
            g = BG_COLOR[1] + int(i/320*15)
            b = BG_COLOR[2] + int(i/320*25)
            draw.line((0, i, 480, i), fill=(r, g, b))
        
        # Header
        draw.rectangle((0, 0, 480, 70), fill=HEADER_COLOR)
        
        # Judul
        title = "SENSOR MONITOR"
        title_width = draw.textlength(title, font=font_title)
        draw.text((480//2 - title_width//2, 35), title, font=font_title, fill=TEXT_COLOR)
        
        # Tentukan sensor yang akan ditampilkan (6 sensor per halaman)
        start_index = page_number * 6
        end_index = min(start_index + 6, len(sensors))
        page_sensors = sensors[start_index:end_index]
        
        # Layout dinamis berdasarkan jumlah sensor
        num_sensors = len(page_sensors)
        panel_height = 0
        
        if num_sensors == 1:
            # Layout full untuk satu sensor
            x = 40
            y = 90
            panel_width = 400
            panel_height = 180
            draw_rounded_panel(draw, x, y, panel_width, panel_height, 15, PANEL_COLOR)
            
            # Tampilkan ikon sensor
            # draw.text((x + 40, y + panel_height//2), page_sensors[0]["icon"], font=font_value, fill=ACCENT_COLOR, anchor="lm")
            
            # Tampilkan nama sensor
            draw.text((x + 120, y + 40), page_sensors[0]["name"], 
                     font=font_label, fill=TEXT_COLOR)
            
            # Tampilkan nilai sensor
            value_color = get_value_color(page_sensors[0])
            value_text = f"{page_sensors[0]['value']} {page_sensors[0]['unit']}"
            draw.text((x + 120, y + 80), value_text, 
                     font=ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 42), 
                     fill=value_color)
            
            # Tampilkan gauge
            draw_gauge(draw, x + 320, y + panel_height//2, 60, 
                      page_sensors[0]["value"], page_sensors[0]["min"], page_sensors[0]["max"], 
                      value_color)
            
        elif num_sensors == 2:
            # Dua panel horizontal
            panel_width = 220
            panel_height = 160
            for i, sensor in enumerate(page_sensors):
                x = 20 + i * 240
                y = 90
                draw_rounded_panel(draw, x, y, panel_width, panel_height, 15, PANEL_COLOR)
                
                # Tampilkan ikon sensor
                # draw.text((x + 30, y + 30), sensor["icon"], font=font_label, fill=ACCENT_COLOR)
                
                # Tampilkan nama sensor
                draw.text((x + 30, y + 70), sensor["name"], 
                         font=font_label, fill=TEXT_COLOR)
                
                # Tampilkan nilai sensor
                value_color = get_value_color(sensor)
                value_text = f"{sensor['value']}"
                draw.text((x + 30, y + 100), value_text, 
                         font=font_value, fill=value_color)
                
                # Tampilkan satuan
                draw.text((x + 30 + draw.textlength(value_text, font=font_value) + 5, y + 105), 
                         sensor["unit"], font=font_unit, fill=(180, 180, 200))
                
                # Tampilkan gauge kecil
                draw_gauge(draw, x + 160, y + 80, 30, 
                          sensor["value"], sensor["min"], sensor["max"], 
                          value_color)
                
        elif num_sensors <= 4:
            # Layout grid 2x2
            panel_width = 210
            panel_height = 110
            for i, sensor in enumerate(page_sensors):
                row = i // 2
                col = i % 2
                x = 30 + col * 220
                y = 90 + row * 120
                draw_rounded_panel(draw, x, y, panel_width, panel_height, 15, PANEL_COLOR)
                
                # Tampilkan ikon sensor
                #draw.text((x + 20, y + 25), sensor["icon"], font=font_label, fill=ACCENT_COLOR)
                
                # Tampilkan nama sensor
                draw.text((x + 20, y + 55), sensor["name"], 
                         font=font_label, fill=TEXT_COLOR)
                
                # Tampilkan nilai sensor
                value_color = get_value_color(sensor)
                value_text = f"{sensor['value']}"
                draw.text((x + 150, y + 35), value_text, 
                         font=font_value, fill=value_color, anchor="ra")
                
                # Tampilkan satuan
                draw.text((x + 150, y + 65), sensor["unit"], 
                         font=font_unit, fill=(180, 180, 200), anchor="ra")
                
        else:  # 5-6 sensors
            # Layout grid 2x3
            panel_width = 210
            panel_height = 90
            for i, sensor in enumerate(page_sensors):
                row = i // 2
                col = i % 2
                x = 30 + col * 220
                y = 90 + row * 100
                draw_rounded_panel(draw, x, y, panel_width, panel_height, 10, PANEL_COLOR)
                
                # Tampilkan ikon sensor
                # draw.text((x + 15, y + 20), sensor["icon"], font=font_label, fill=ACCENT_COLOR)
                
                # Tampilkan nama sensor
                name_text = sensor["name"][:12] + "..." if len(sensor["name"]) > 12 else sensor["name"]
                draw.text((x + 15, y + 50), name_text, 
                         font=ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18), 
                         fill=TEXT_COLOR)
                
                # Tampilkan nilai sensor
                value_color = get_value_color(sensor)
                value_text = f"{sensor['value']}"
                draw.text((x + 170, y + 35), value_text, 
                         font=font_value, fill=value_color, anchor="ra")
                
                # Tampilkan satuan
                draw.text((x + 170, y + 65), sensor["unit"], 
                         font=font_unit, fill=(180, 180, 200), anchor="ra")
        
        # Footer dengan informasi halaman
        total_pages = (len(sensors) + 5) // 6
        page_text = f"Page {page_number+1} of {total_pages}"
        page_width = draw.textlength(page_text, font=font_page)
        
        # Panel footer
        draw_rounded_panel(draw, 480//2 - page_width//2 - 15, 280, 
                          page_width + 30, 30, 15, HEADER_COLOR)
        draw.text((480//2, 295), page_text, font=font_page, fill=TEXT_COLOR, anchor="mm")
        
        # Tampilkan waktu saat ini
        time_text = time.strftime("%H:%M:%S")
        draw.text((480 - 20, 295), time_text, font=font_time, fill=(180, 220, 240), anchor="rm")
        
        # Indikator status
        status_color = HIGHLIGHT_COLOR
        for sensor in sensors:
            if sensor["value"] < sensor["warn_min"] or sensor["value"] > sensor["warn_max"]:
                status_color = WARNING_COLOR
                break
        draw.ellipse((20, 290, 40, 310), fill=status_color)
        
        # Tampilkan countdown pergantian halaman
        countdown_text = f"Next: {time_left}s"
        draw.text((20, 295), countdown_text, font=font_countdown, fill=(200, 200, 100), anchor="lm")

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
