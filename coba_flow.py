from pymodbus.client import ModbusSerialClient


def read_sensor_data(client, unit_id=1):
    data = {}

    # Water Level (0x03EB)
    res_level = client.read_holding_registers(address=0x03EB, count=1, unit=unit_id)
    if not res_level.isError():
        data["water_level_mm"] = res_level.registers[0]

    # Velocity (0x03EC)
    res_velocity = client.read_holding_registers(address=0x03EC, count=1, unit=unit_id)
    if not res_velocity.isError():
        velocity_cms = res_velocity.registers[0]
        data["velocity_cms"] = velocity_cms
        data["velocity_ms"] = velocity_cms / 100.0

    # Instantaneous Flow (0x03EA)
    res_flow = client.read_holding_registers(address=0x03EA, count=1, unit=unit_id)
    if not res_flow.isError():
        data["flow_m3s"] = res_flow.registers[0] / 1000.0

    return data


def set_section_config(client, unit_id, section_type, size1=0, size2=0, size3=0):
    # Section type
    res = client.write_register(address=0x0412, value=section_type, unit=unit_id)
    if res.isError():
        print("❌ Gagal set section type")
        return False

    if section_type == 1:  # Trapezoid
        client.write_register(address=0x0413, value=size1)
        client.write_register(address=0x0414, value=size2)
        client.write_register(address=0x0415, value=size3)
        print(
            f"✅ Trapezoid diset: Tinggi={size1} mm, Lereng={size2} mm, Dasar={size3} mm"
        )

    elif section_type == 2:  # Rectangle
        client.write_register(address=0x0413, value=size1)
        client.write_register(address=0x0415, value=size3)
        print(f"✅ Rectangle diset: Tinggi={size1} mm, Dasar={size3} mm")

    return True


if __name__ == "__main__":
    client = ModbusSerialClient(
        port="/dev/ttyUSB0",  # atau 'COM3' di Windows
        baudrate=9600,
        stopbits=1,
        bytesize=8,
        parity="N",
        timeout=1,
    )

    if client.connect():
        print("✅ Terhubung ke sensor RS-RAD-N01-3")
        unit_id = 1  # default Modbus address

        # Baca sensor
        sensor_data = read_sensor_data(client, unit_id)
        print("📡 Data Sensor:", sensor_data)

        # Set ke trapezoid
        # set_section_config(
        #    client, unit_id, section_type=1, size1=2000, size2=500, size3=1000
        # )

        # Set ke rectangle
        set_section_config(
            client, unit_id, section_type=2, size1=200, size2=0, size3=450
        )

        client.close()
    else:
        print("❌ Tidak bisa konek ke sensor")
