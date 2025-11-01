import minimalmodbus

# Inisialisasi RS485 Modbus RTU
instrument = minimalmodbus.Instrument("/dev/ttyUSB1", 1)
instrument.serial.baudrate = 4800
instrument.serial.bytesize = 8
instrument.serial.parity = "N"
instrument.serial.stopbits = 1
instrument.serial.timeout = 1


def read_depth():
    """Baca jarak sensor->permukaan air & hitung kedalaman air dari dasar"""
    try:
        # Register 1003 = current water level (distance sensor→permukaan air, mm)
        distance_to_water_mm = instrument.read_register(1003, 0, functioncode=3)

        # Register 1058 = Water level range (jarak sensor→dasar saluran, mm)
        distance_to_bottom_mm = instrument.read_register(1058, 0, functioncode=3)

        # Hitung kedalaman air dari dasar
        # depth = (sensor→dasar) - (sensor→permukaan air)
        depth_mm = max(distance_to_bottom_mm - distance_to_water_mm, 0)

        return {
            "distance_to_water_mm": distance_to_water_mm,
            "distance_to_bottom_mm": distance_to_bottom_mm,
            "depth_mm": depth_mm,
            "depth_cm": depth_mm / 10.0,
            "depth_m": depth_mm / 1000.0,
        }
    except Exception as e:
        print("❌ Error baca depth:", e)
        return None


def read_sensor_data():
    """Baca semua data sensor"""
    data = {}

    try:
        # Baca depth (water level dari dasar)
        depth_info = read_depth()
        if depth_info:
            data.update(depth_info)
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


def set_section_config():
    """Konfigurasi penampang trapezoid sesuai data Anda"""
    try:
        # Section type: 1=Trapezoid
        instrument.write_register(1042, 1, functioncode=6)

        # Section parameters untuk trapezoid
        # Size1 = tinggi saluran = 2800 mm
        # instrument.write_register(1043, 2500, functioncode=6)
        instrument.write_register(1043, 6000, functioncode=6)

        # Size2 = lebar slope = 1000 mm
        # instrument.write_register(1044, 1000, functioncode=6)
        instrument.write_register(1044, 750, functioncode=6)

        # Size3 = lebar dasar = 9600 mm
        instrument.write_register(1045, 4500, functioncode=6)

        # Water level range (jarak sensor→dasar)
        # Sensor ke penampang atas = 700mm, tinggi penampang 2800mm
        # Jadi sensor→dasar = 700 + 2800 = 3500mm
        instrument.write_register(1058, 2300, functioncode=6)

        print("✅ Trapezoid configured: Tinggi=2800mm, Slope=1000mm, Dasar=9600mm")
        print("✅ Water level range set to 3500mm (sensor→dasar)")
        return True
    except Exception as e:
        print("❌ Gagal set section config:", e)
        return False


def debug_registers():
    """Debug: baca semua register penting untuk verifikasi"""
    registers_to_check = {
        1003: "Current Water Level (distance to water)",
        1004: "Current Flow Rate",
        1005: "Current Velocity",
        1042: "Section Type",
        1043: "Section Size1",
        1044: "Section Size2",
        1045: "Section Size3",
        1058: "Water Level Range (distance to bottom)",
    }

    print("\n🔍 Debug Register Values:")
    for addr, desc in registers_to_check.items():
        try:
            value = instrument.read_register(addr, 0, functioncode=3)
            print(f"Register {addr} ({desc}): {value}")
        except Exception as e:
            print(f"❌ Gagal baca register {addr}: {e}")


if __name__ == "__main__":
    print("✅ Terhubung ke sensor RS-RAD-N01-3")

    # 1. Set konfigurasi penampang
    set_section_config()

    # 2. Debug baca register
    debug_registers()

    # 3. Baca data sensor
    sensor_data = read_sensor_data()
    print("\n📡 Data Sensor:")
    for key, value in sensor_data.items():
        print(f"  {key}: {value}")
