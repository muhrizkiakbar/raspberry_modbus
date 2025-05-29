import json
import time
import logging
from threading import Thread
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from database import SecureDatabase
from auth import AuthenticationSystem
from ota import OTAManager
from web import WebServer
from calibration import SensorCalibrator


class RTUSystem:
    def __init__(self):
        self.load_config()
        self.init_logging()
        self.db = SecureDatabase(self.config)
        self.auth = AuthenticationSystem(self.config)
        self.ota = OTAManager(self.config, self.auth)
        self.web = WebServer(self.config, self.db, self.auth)
        self.modbus = self.init_modbus()
        self.calibrators = self.init_calibrators()
        self.running = True

    def load_config(self):
        with open("config.json") as f:
            self.config = json.load(f)

    def init_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("rtu.log"), logging.StreamHandler()],
        )

    def init_modbus(self):
        return ModbusSerialClient(
            method="rtu",
            port=self.config["modbus"]["port"],
            baudrate=self.config["modbus"]["baudrate"],
            parity=self.config["modbus"]["parity"],
            stopbits=self.config["modbus"]["stopbits"],
            bytesize=self.config["modbus"]["bytesize"],
            timeout=self.config["modbus"]["timeout"],
        )

    def init_calibrators(self):
        return {
            name: SensorCalibrator(cfg)
            for name, cfg in self.config["sensors"]["analog"].items()
        }

    def start(self):
        if self.db.connect():
            self.start_services()
            self.main_loop()

    def start_services(self):
        if self.config["http"]["enabled"]:
            Thread(target=self.web.start, daemon=True).start()

        if self.config["ota"]["enabled"]:
            Thread(target=self.ota.start_update_check, daemon=True).start()

    def main_loop(self):
        while self.running:
            try:
                data = self.read_sensors()
                if data:
                    self.process_data(data)
                time.sleep(1)
            except KeyboardInterrupt:
                self.shutdown()
            except Exception as e:
                logging.error(f"Main loop error: {e}")
                self.enter_safe_mode()

    def read_sensors(self):
        data = {}
        try:
            if self.modbus.connect():
                data.update(self.read_analog_sensors())
                data.update(self.read_digital_sensors())
                self.modbus.close()
        except ModbusException as e:
            logging.error(f"Modbus connection error: {e}")
        return data

    def read_analog_sensors(self):
        analog_data = {}
        for name, cfg in self.config["sensors"]["analog"].items():
            try:
                response = self.modbus.read_input_registers(
                    cfg["address"], 1, slave=self.config["modbus"]["slave_id"]
                )
                if not response.isError():
                    raw_value = response.registers[0]
                    analog_data[name] = self.calibrators[name].apply(raw_value)
            except Exception as e:
                logging.error(f"Analog sensor {name} error: {e}")
        return analog_data

    def read_digital_sensors(self):
        digital_data = {}
        for name, cfg in self.config["sensors"]["digital"].items():
            try:
                response = self.modbus.read_discrete_inputs(
                    cfg["address"], 1, slave=self.config["modbus"]["slave_id"]
                )
                if not response.isError():
                    digital_data[name] = int(response.bits[0])
            except Exception as e:
                logging.error(f"Digital sensor {name} error: {e}")
        return digital_data

    def process_data(self, data):
        self.db.insert_data(data)
        self.check_alarms(data)
        self.publish_mqtt(data)

    def check_alarms(self, data):
        for sensor, value in data.items():
            alarm_cfg = self.config["alarms"].get(sensor)
            if alarm_cfg:
                if "max" in alarm_cfg and value > alarm_cfg["max"]:
                    self.trigger_alarm(sensor, f"High limit exceeded: {value}")
                elif "min" in alarm_cfg and value < alarm_cfg["min"]:
                    self.trigger_alarm(sensor, f"Low limit exceeded: {value}")
                elif "trigger" in alarm_cfg and value == alarm_cfg["trigger"]:
                    self.trigger_alarm(sensor, "Trigger activated")

    def trigger_alarm(self, sensor, message):
        logging.warning(f"ALARM: {sensor} - {message}")
        self.db.log_alarm(sensor, message)
        self.publish_mqtt({"alarm": {sensor: message}})

    def publish_mqtt(self, data):
        if self.config["mqtt"]["enabled"]:
            try:
                payload = json.dumps(data)
                self.mqtt.publish(self.config["mqtt"]["topic"], payload)
            except Exception as e:
                logging.error(f"MQTT publish error: {e}")

    def enter_safe_mode(self):
        logging.critical("Entering safe mode!")
        self.config["mqtt"]["enabled"] = False
        self.config["ota"]["enabled"] = False
        self.db.backup()

    def shutdown(self):
        self.running = False
        self.modbus.close()
        self.db.close()
        logging.info("System shutdown complete")


if __name__ == "__main__":
    rtu = RTUSystem()
    rtu.start()
