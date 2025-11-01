import minimalmodbus

# Inisialisasi RS485 Modbus RTU
instrument = minimalmodbus.Instrument("/dev/ttyUSB1", 1)  # (port, slave address)
instrument.serial.baudrate = 4800  # sesuaikan dengan sensor (default bisa 4800/9600)
instrument.serial.bytesize = 8
instrument.serial.parity = "N"
instrument.serial.stopbits = 1
instrument.serial.timeout = 1


def read_depth():
    """Baca jarak sensor->permukaan air & hitung kedalaman air dari dasar"""
    try:
        # Register 1003 = current water level (distance sensor→air, mm)
        distance_mm = instrument.read_register(1003, 0, functioncode=3)

        # Register 1043 = channel height (sensor→dasar, mm)
        channel_height_mm = instrument.read_register(1043, 0, functioncode=3)

        # Hitung kedalaman
        depth_mm = max(channel_height_mm - distance_mm, 0)
        # depth_mm = 65535 - (distance_mm - channel_height_mm)
        # depth_mm = channel_height_mm - distance_mm
        # depth_mm = 65535 - (distance_mm + channel_height_mm + 100)

        return {
            "distance_mm": distance_mm,
            "channel_height_mm": channel_height_mm,
            "depth_mm": depth_mm,
            "depth_cm": depth_mm / 10.0,
            "depth_m": depth_mm / 1000.0,
        }
    except Exception as e:
        print("❌ Error baca depth:", e)
        return None


def read_sensor_data():
    """Baca water level, velocity, dan flow dari sensor"""
    data = {}

    try:
        # Water Level (0x03EB = 1003)
        # water_level = instrument.read_register(1003, 0, functioncode=3)
        # data["water_level_mm"] = 65535 - water_level
        data["water_level_mm"] = read_depth()
    except Exception as e:
        print("❌ Gagal baca Water Level:", e)

    try:
        # Velocity (0x03EC = 1004) -> cm/s
        velocity_cms = instrument.read_register(1004, 0, functioncode=3)
        data["velocity_cms"] = velocity_cms
        data["velocity_ms"] = velocity_cms / 100.0
    except Exception as e:
        print("❌ Gagal baca Velocity:", e)

    try:
        # Instantaneous Flow (0x03EA = 1002) -> m³/s * 1000
        flow_raw = instrument.read_register(1002, 0, functioncode=3)
        data["flow_m3s"] = flow_raw / 1000.0
    except Exception as e:
        print("❌ Gagal baca Flow:", e)

    return data


def set_section_config(section_type, size1=0, size2=0, size3=0):
    """
    Konfigurasi bentuk penampang saluran pada sensor RS-RAD-N01-3
    section_type: 1=Trapezoid, 2=Rectangle
    """
    try:
        # Section type (0x0412 = 1042 decimal)
        instrument.write_register(1042, section_type, functioncode=6)

        if section_type == 1:  # Trapezoid
            instrument.write_register(1043, size1, functioncode=6)  # size1 = tinggi
            instrument.write_register(
                1044, size2, functioncode=6
            )  # size2 = lebar lereng
            instrument.write_register(
                1045, size3, functioncode=6
            )  # size3 = lebar dasar
            print(
                f"✅ Trapezoid diset: Tinggi={size1} mm, Lereng={size2} mm, Dasar={size3} mm"
            )

        elif section_type == 2:  # Rectangle
            instrument.write_register(1043, size1, functioncode=6)  # size1 = tinggi
            instrument.write_register(
                1045, size3, functioncode=6
            )  # size3 = lebar dasar
            print(f"✅ Rectangle diset: Tinggi={size1} mm, Dasar={size3} mm")

        return True
    except Exception as e:
        print("❌ Gagal set section config:", e)
        return False


if __name__ == "__main__":
    print("✅ Terhubung ke sensor RS-RAD-N01-3")

    # Contoh Rectangle (size1tinggi=200mm, size3dasar=450mm)
    set_section_config(section_type=1, size1=1300, size2=750, size3=6000)

    sensor_data = read_sensor_data()
    print("📡 Data Sensor:", sensor_data)
