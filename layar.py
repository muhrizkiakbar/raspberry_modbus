"""
3.5 inch 480x320 TFT with SPI ILI9488
on Raspberry Pi 4B using Python/luma.lcd
Hello World with color/pwm backlight test.
"""

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import ili9488
from PIL import ImageFont
import time

serial = spi(port=0, device=0, gpio_DC=23, gpio_RST=24)
device = ili9488(serial, rotate=2,
                 gpio_LIGHT=18, active_low=False) # BACKLIGHT PIN = GPIO 18, active High)

font_FreeMonoBold_30 = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf", 30)
font_FreeSansBold_20 = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20)
font_FreeSerifBoldItalic_30 = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf", 30)

device.backlight(True) # Turn on backlight using luma device.backlight()

with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="black")
    draw.text((30, 40), "Hello World", font=font_FreeSerifBoldItalic_30, fill="white")

time.sleep(3)
with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="red")
    draw.text((30, 40), "red", font=font_FreeMonoBold_30, fill="white")

time.sleep(3)
with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="green")
    draw.text((30, 40), "green", font=font_FreeMonoBold_30, fill="white")
    
time.sleep(3)
with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="blue")
    draw.text((30, 40), "blue", font=font_FreeMonoBold_30, fill="white")

time.sleep(3)
with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="black")
    draw.text((10, 40), "Test backlight using GPIO.PWM", font=font_FreeMonoBold_30, fill="white")
    
#=== Test control BACKLIGHT_PIN using GPIO.PWM ===
import RPi.GPIO as GPIO

BACKLIGHT_PIN = 18

#GPIO.setmode(GPIO.BCM)
#GPIO.setup(BACKLIGHT_PIN, GPIO.OUT)

pwm = GPIO.PWM(BACKLIGHT_PIN, 1000)
pwm.start(0)

def fade_in():
    for duty_cycle in range(0, 101, 1):
        pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(0.01)

def fade_out():
    for duty_cycle in range(100, -1, -1):
        pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(0.01)

while True:
    fade_in()
    time.sleep(1)
    fade_out()
    time.sleep(1)

pwm.stop()
GPIO.cleanup()
