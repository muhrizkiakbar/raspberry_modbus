from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import ili9488
from PIL import Image, ImageDraw, ImageFont
import time
import math


class Display:
    def __init__(self):
        # Initialize device
        self.serial = spi(port=0, device=0, gpio_DC=23, gpio_RST=24)
        self.device = ili9488(self.serial, rotate=2, gpio_LIGHT=18, active_low=False)
        self.device.backlight(True)

        # Fonts for display
        self.font_title = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 26
        )
        self.font_label = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20
        )
        self.font_value = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 24
        )
        self.font_unit = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18
        )
        self.font_page = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 20
        )
        self.font_time = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18
        )
        self.font_countdown = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 16
        )

        # Color theme
        self.BG_COLOR = (15, 25, 35)  # Dark blue
        self.HEADER_COLOR = (0, 90, 130)  # Deep blue
        self.PANEL_COLOR = (35, 70, 100)  # Medium blue
        self.TEXT_COLOR = (230, 230, 230)  # Light gray
        self.HIGHLIGHT_COLOR = (0, 200, 255)  # Bright blue
        self.WARNING_COLOR = (255, 90, 90)  # Red for warnings
        self.ACCENT_COLOR = (0, 180, 180)  # Teal accent

    def draw_rounded_panel(self, draw, x, y, width, height, radius, color):
        """Draw a rounded rectangle panel"""
        # Main rectangle
        draw.rectangle((x + radius, y, x + width - radius, y + height), fill=color)
        draw.rectangle((x, y + radius, x + width, y + height - radius), fill=color)

        # Rounded corners
        draw.pieslice([x, y, x + 2 * radius, y + 2 * radius], 180, 270, fill=color)
        draw.pieslice(
            [x + width - 2 * radius, y, x + width, y + 2 * radius], 270, 360, fill=color
        )
        draw.pieslice(
            [x, y + height - 2 * radius, x + 2 * radius, y + height],
            90,
            180,
            fill=color,
        )
        draw.pieslice(
            [x + width - 2 * radius, y + height - 2 * radius, x + width, y + height],
            0,
            90,
            fill=color,
        )

    def get_value_color(self, sensor):
        """Determine text color based on sensor status"""
        if sensor["status"] != "OK":
            return self.WARNING_COLOR
        return self.HIGHLIGHT_COLOR

    def display_sensor_page(self, sensor_data, current_page, time_left):
        """
        Display a page of sensor data on the LCD

        Args:
            sensor_data (list): Raw sensor data in dictionary format
            current_page (int): Current page number (0-indexed)
            time_left (int): Time left for page switch in seconds
        """
        # Transform sensor data to expected format
        sensors = []
        for item in sensor_data:
            name = list(item.keys())[0]
            data = item[name]
            sensors.append(
                {
                    "name": name.upper(),
                    "unit": data["unit"],
                    "value": data["value"],
                    "status": data["status"],
                    "sensor_type": data["sensor_type"],
                }
            )

        with canvas(self.device) as draw:
            # Background
            draw.rectangle(self.device.bounding_box, fill=self.BG_COLOR)

            # Header
            header_height = 50
            draw.rectangle((0, 0, 480, header_height), fill=self.HEADER_COLOR)

            # Title
            title = "SENSOR MONITOR"
            title_width = draw.textlength(title, font=self.font_title)
            draw.text(
                (480 // 2 - title_width // 2, 25),
                title,
                font=self.font_title,
                fill=self.TEXT_COLOR,
            )

            # Determine sensors to show (6 per page)
            start_index = current_page * 6
            end_index = min(start_index + 6, len(sensors))
            page_sensors = sensors[start_index:end_index]
            num_sensors = len(page_sensors)

            # Layout based on number of sensors
            if num_sensors == 1:
                # Single sensor layout
                x, y = 20, 60
                panel_width, panel_height = 440, 200
                self.draw_rounded_panel(
                    draw, x, y, panel_width, panel_height, 10, self.PANEL_COLOR
                )

                # Sensor name
                draw.text(
                    (x + 20, y + 20),
                    page_sensors[0]["name"],
                    font=self.font_label,
                    fill=self.TEXT_COLOR,
                )

                # Sensor type
                type_text = f"Type: {page_sensors[0]['sensor_type']}"
                draw.text(
                    (x + 20, y + 50),
                    type_text,
                    font=self.font_unit,
                    fill=self.TEXT_COLOR,
                )

                # Sensor value
                value_color = self.get_value_color(page_sensors[0])
                value_text = f"{page_sensors[0]['value']}"
                value_font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 36
                )
                value_width = draw.textlength(value_text, font=value_font)
                draw.text(
                    (x + panel_width // 2 - value_width // 2, y + 100),
                    value_text,
                    font=value_font,
                    fill=value_color,
                )

                # Unit (ditempatkan di bawah nama sensor)
                unit_text = f"Unit: {page_sensors[0]['unit']}"
                unit_width = draw.textlength(unit_text, font=self.font_label)
                draw.text(
                    (x + 20, y + 150),
                    unit_text,
                    font=self.font_label,
                    fill=self.TEXT_COLOR,
                )

                # Status indicator
                status = page_sensors[0]["status"]
                status_color = (
                    self.HIGHLIGHT_COLOR if status == "OK" else self.WARNING_COLOR
                )
                status_text = f"Status: {status}"
                status_width = draw.textlength(status_text, font=self.font_label)
                draw.text(
                    (x + panel_width - status_width - 20, y + 150),
                    status_text,
                    font=self.font_label,
                    fill=status_color,
                )
            else:
                # Grid layout (3x2)
                cols = 2
                rows = 3
                panel_width = 220
                panel_height = 75
                panel_spacing = 5

                for i, sensor in enumerate(page_sensors):
                    row = i // cols
                    col = i % cols
                    x = 20 + col * (panel_width + panel_spacing)
                    y = 60 + row * (panel_height + panel_spacing)

                    # Skip if panel would go off-screen
                    if y + panel_height > 310:
                        continue

                    self.draw_rounded_panel(
                        draw, x, y, panel_width, panel_height, 8, self.PANEL_COLOR
                    )

                    # Sensor name (top left)
                    name_text = sensor["name"]
                    if draw.textlength(name_text, font=self.font_label) > 140:
                        name_text = (
                            name_text[:12] + "..." if len(name_text) > 12 else name_text
                        )
                    draw.text(
                        (x + 10, y + 10),
                        name_text,
                        font=self.font_label,
                        fill=self.TEXT_COLOR,
                    )

                    # Unit (di bawah nama sensor, kiri)
                    value_color = self.get_value_color(sensor)
                    value_text = f"{sensor['value']}"
                    value_width = draw.textlength(value_text, font=self.font_value)
                    draw.text(
                        (x + panel_width - value_width - 10, y + 10),
                        sensor["unit"],
                        font=self.font_unit,
                        fill=(180, 180, 200),
                    )

                    # Sensor value (top right)
                    draw.text(
                        (x + 10, y + 40),
                        value_text,
                        font=self.font_value,
                        fill=value_color,
                    )

                    # Status (bottom right)
                    status = sensor["status"]
                    status_color = (
                        self.HIGHLIGHT_COLOR if status == "OK" else self.WARNING_COLOR
                    )
                    status_width = draw.textlength(status, font=self.font_unit)
                    draw.text(
                        (x + panel_width - status_width - 10, y + 40),
                        status,
                        font=self.font_unit,
                        fill=status_color,
                    )

            # Footer
            footer_height = 30
            footer_y = 320 - footer_height
            draw.rectangle((0, footer_y, 480, 320), fill=self.HEADER_COLOR)

            # Page info
            total_pages = (len(sensors) + 5) // 6
            page_text = f"Page {current_page + 1}/{total_pages}"
            page_width = draw.textlength(page_text, font=self.font_page)
            draw.text(
                (20, footer_y + footer_height // 2),
                page_text,
                font=self.font_page,
                fill=self.TEXT_COLOR,
                anchor="lm",
            )

            # Current time
            time_text = time.strftime("%H:%M:%S")
            time_width = draw.textlength(time_text, font=self.font_time)
            draw.text(
                (480 - 20, footer_y + footer_height // 2),
                time_text,
                font=self.font_time,
                fill=self.TEXT_COLOR,
                anchor="rm",
            )

            # System status indicator
            status_color = self.HIGHLIGHT_COLOR
            for sensor in sensors:
                if sensor["status"] != "OK":
                    status_color = self.WARNING_COLOR
                    break
            draw.ellipse(
                (480 // 2 - 15, footer_y + 7, 480 // 2 + 15, footer_y + 23),
                fill=status_color,
            )

            # Page change countdown
            countdown_text = f"Next: {time_left}s"
            countdown_width = draw.textlength(countdown_text, font=self.font_countdown)
            draw.text(
                (480 // 2 - countdown_width // 2, footer_y + footer_height // 2),
                countdown_text,
                font=self.font_countdown,
                fill=(200, 200, 100),
                anchor="lm",
            )

    def cleanup(self):
        """Clean up device resources"""
        self.device.backlight(False)
        self.device.cleanup()
