from pymodbus.client import ModbusSerialClient


def read_sensor_data(client, slave_id=1):
    """Baca water level, velocity, dan flow dari sensor"""
    data = {}

    # Water Level (0x03EB)
    res_level = client.read_holding_registers(address=0x03EB, count=1, slave=slave_id)
    if not res_level.isError():
        data["water_level_mm"] = res_level.registers[0]
    else:
        print("❌ Gagal baca Water Level")

    # Velocity (0x03EC)
    res_velocity = client.read_holding_registers(
        address=0x03EC, count=1, slave=slave_id
    )
    if not res_velocity.isError():
        velocity_cms = res_velocity.registers[0]
        data["velocity_cms"] = velocity_cms
        data["velocity_ms"] = velocity_cms / 100.0  # cm/s → m/s
    else:
        print("❌ Gagal baca Velocity")

    # Instantaneous Flow (0x03EA)
    res_flow = client.read_holding_registers(address=0x03EA, count=1, slave=slave_id)
    if not res_flow.isError():
        flow_raw = res_flow.registers[0]
        data["flow_m3s"] = flow_raw / 1000.0  # dibagi 1000
    else:
        print("❌ Gagal baca Flow")

    return data


def set_section_config(client, slave_id, section_type, size1=0, size2=0, size3=0):
    """
    Konfigurasi bentuk penampang saluran pada sensor RS-RAD-N01-3
    Args:
        section_type: 1=Trapezoid, 2=Rectangle
        size1: tinggi saluran (mm)
        size2: lebar lereng (mm, hanya untuk trapezoid)
        size3: lebar dasar (mm)
    """
    # Section type
    res = client.write_register(address=0x0412, value=section_type, slave=slave_id)
    if res.isError():
        print("❌ Gagal set section type")
        return False

    if section_type == 1:  # Trapezoid
        client.write_register(address=0x0413, value=size1, slave=slave_id)
        client.write_register(address=0x0414, value=size2, slave=slave_id)
        client.write_register(address=0x0415, value=size3, slave=slave_id)
        print(
            f"✅ Trapezoid diset: Tinggi={size1} mm, Lereng={size2} mm, Dasar={size3} mm"
        )

    elif section_type == 2:  # Rectangle
        client.write_register(address=0x0413, value=size1, slave=slave_id)
        client.write_register(address=0x0415, value=size3, slave=slave_id)
        print(f"✅ Rectangle diset: Tinggi={size1} mm, Dasar={size3} mm")

    return True


if __name__ == "__main__":
    client = ModbusSerialClient(
        port="/dev/ttyUSB0",  # ganti dengan 'COM3' kalau di Windows
        baudrate=9600,
        stopbits=1,
        bytesize=8,
        parity="N",
        timeout=1,
    )

    if client.connect():
        print("✅ Terhubung ke sensor RS-RAD-N01-3")
        slave_id = 1  # default address 0x01

        # --- BACA DATA SENSOR ---
        sensor_data = read_sensor_data(client, slave_id)
        print("📡 Data Sensor:")
        print(f"   Water Level : {sensor_data.get('water_level_mm', '-')} mm")
        print(
            f"   Velocity    : {sensor_data.get('velocity_cms', '-')} cm/s "
            f"({sensor_data.get('velocity_ms', '-')} m/s)"
        )
        print(f"   Flow        : {sensor_data.get('flow_m3s', '-')} m³/s")

        # --- KONFIGURASI PENAMPANG ---
        # Contoh: Trapezoid (tinggi=2000mm, lereng=500mm, dasar=1000mm)
        set_section_config(
            client, slave_id, section_type=2, size1=250, size2=0, size3=450
        )

        # Contoh: Rectangle (tinggi=2000mm, dasar=1500mm)
        set_section_config(client, slave_id, section_type=2, size1=2000, size3=1500)

        client.close()
    else:
        print("❌ Tidak bisa konek ke sensor")
