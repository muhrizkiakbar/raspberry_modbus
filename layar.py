import pygame
import random
import time
import os

# Konfigurasi untuk layar SPI
os.environ["SDL_FBDEV"] = "/dev/fb0"
os.environ["SDL_MOUSEDEV"] = "/dev/input/touchscreen"
os.environ["SDL_MOUSEDRV"] = "TSLIB"

# Inisialisasi Pygame
pygame.init()

# Ukuran layar ILI9488
WIDTH = 480
HEIGHT = 320
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.mouse.set_visible(False)

# Warna
BACKGROUND = (0, 0, 50)
TEXT_COLOR = (255, 255, 255)
HIGHLIGHT_COLOR = (0, 255, 255)
BOX_COLOR = (0, 50, 100)

# Font
title_font = pygame.font.SysFont('Arial', 28, bold=True)
sensor_font = pygame.font.SysFont('Arial', 24)
unit_font = pygame.font.SysFont('Arial', 18)

# Daftar sensor
sensors = [
    {"name": "pH", "unit": "", "value": 0.0},
    {"name": "TDS", "unit": "ppm", "value": 0.0},
    {"name": "TSS", "unit": "mg/L", "value": 0.0},
    {"name": "Water Level", "unit": "cm", "value": 0.0},
    {"name": "Flow Meter", "unit": "L/min", "value": 0.0},
    {"name": "Velocity", "unit": "m/s", "value": 0.0},
    {"name": "Debit", "unit": "m³/s", "value": 0.0}
]

# Grup sensor untuk rotasi
sensor_groups = []
for i in range(0, len(sensors), 6):
    group = sensors[i:i+6]
    if len(group) < 6 and i > 0:
        # Tambahkan sensor dari awal jika grup terakhir kurang dari 6
        group += sensors[0:6-len(group)]
    sensor_groups.append(group)

current_group = 0
last_change = time.time()

def draw_sensor_box(surface, sensor, x, y, width, height):
    # Gambar kotak sensor
    pygame.draw.rect(surface, BOX_COLOR, (x, y, width, height), 0, 10)
    pygame.draw.rect(surface, HIGHLIGHT_COLOR, (x, y, width, height), 2, 10)
    
    # Render nama sensor
    name_surf = sensor_font.render(sensor["name"], True, HIGHLIGHT_COLOR)
    name_rect = name_surf.get_rect(center=(x + width//2, y + 30))
    surface.blit(name_surf, name_rect)
    
    # Render nilai sensor
    value_text = f"{sensor['value']:.2f}" if isinstance(sensor['value'], float) else f"{sensor['value']}"
    value_surf = title_font.render(value_text, True, TEXT_COLOR)
    value_rect = value_surf.get_rect(center=(x + width//2, y + height//2))
    surface.blit(value_surf, value_rect)
    
    # Render unit
    unit_surf = unit_font.render(sensor["unit"], True, HIGHLIGHT_COLOR)
    unit_rect = unit_surf.get_rect(center=(x + width//2, y + height - 25))
    surface.blit(unit_surf, unit_rect)

def update_sensor_values():
    # Simulasi pembacaan sensor (dalam aplikasi nyata, ganti dengan pembacaan sebenarnya)
    for sensor in sensors:
        if sensor["name"] == "pH":
            sensor["value"] = round(random.uniform(0.0, 14.0), 1)
        elif sensor["name"] == "TDS":
            sensor["value"] = random.randint(0, 1000)
        elif sensor["name"] == "TSS":
            sensor["value"] = random.randint(0, 500)
        elif sensor["name"] == "Water Level":
            sensor["value"] = random.randint(0, 200)
        elif sensor["name"] == "Flow Meter":
            sensor["value"] = round(random.uniform(0.0, 100.0), 1)
        elif sensor["name"] == "Velocity":
            sensor["value"] = round(random.uniform(0.0, 5.0), 2)
        elif sensor["name"] == "Debit":
            sensor["value"] = round(random.uniform(0.0, 10.0), 3)

# Loop utama
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
    
    # Update nilai sensor setiap iterasi
    update_sensor_values()
    
    # Ganti grup setiap 5 detik
    if time.time() - last_change > 5:
        current_group = (current_group + 1) % len(sensor_groups)
        last_change = time.time()
    
    # Bersihkan layar
    screen.fill(BACKGROUND)
    
    # Judul
    title = title_font.render("SISTEM MONITORING SENSOR AIR", True, HIGHLIGHT_COLOR)
    screen.blit(title, (WIDTH//2 - title.get_rect().width//2, 10))
    
    # Gambar kotak sensor
    group = sensor_groups[current_group]
    for i, sensor in enumerate(group):
        row = i // 2
        col = i % 2
        x = 20 + col * (WIDTH//2 - 10)
        y = 60 + row * (HEIGHT//3 - 20)
        draw_sensor_box(screen, sensor, x, y, WIDTH//2 - 30, HEIGHT//3 - 20)
    
    # Tampilkan halaman
    page_text = f"Halaman {current_group + 1}/{len(sensor_groups)}"
    page_surf = unit_font.render(page_text, True, HIGHLIGHT_COLOR)
    screen.blit(page_surf, (WIDTH - page_surf.get_width() - 10, HEIGHT - 20))
    
    pygame.display.flip()
    pygame.time.delay(100)

pygame.quit()
