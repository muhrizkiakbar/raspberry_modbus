import serial
import time
import crcmod

for baud in [4800, 9600, 19200, 38400, 57600, 115200]:
    print(f"\nTrying baudrate: {baud}")
    try:
        port = serial.Serial(
            "/dev/ttyUSB0",
            baudrate=baud,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=0.5,
        )

        # Test Modbus read command
        command = b"\x01\x03\x03\xeb\x00\x01"  # Tanpa CRC
        crc = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)(command)
        full_command = command + crc.to_bytes(2, "little")

        print(f"Sending: {full_command.hex().upper()}")
        port.write(full_command)

        time.sleep(0.2)
        response = port.read(7)
        print(f"Received: {response.hex().upper() if response else 'No response'}")

        port.close()
    except Exception as e:
        print(f"Error at {baud} baud: {str(e)}")
