import logging
import numpy as np


class SensorCalibrator:
    def __init__(self, sensor_config):
        self.config = sensor_config.get("calibration", {})
        self.unit = sensor_config["unit"]

    def apply_calibration(self, raw_value):
        try:
            # Konversi dasar ke unit engineering
            base_value = self._convert_to_engineering(raw_value)

            # Terapkan kalibrasi
            if self.config.get("type") == "linear":
                return self._linear_calibration(base_value)
            elif self.config.get("type") == "poly":
                return self._polynomial_calibration(base_value)
            else:
                return base_value

        except Exception as e:
            logging.error(f"Calibration failed: {e}")
            return None

    def _convert_to_engineering(self, raw_value):
        """Konversi raw ADC ke unit dasar"""
        adc_resolution = 65535  # 16-bit

        if self.unit == "V":
            return (raw_value / adc_resolution) * 5.0
        elif self.unit == "mA":
            return ((raw_value / adc_resolution) * 16.0) + 4.0
        else:
            raise ValueError(f"Unknown unit: {self.unit}")

    def _linear_calibration(self, value):
        """Kalibrasi linear: y = (x * gain) + offset"""
        params = self.config["parameters"]
        calibrated = (value * params["gain"]) + params["offset"]

        # Validasi range
        if "valid_range" in self.config:
            min_val, max_val = self.config["valid_range"]
            if not (min_val <= calibrated <= max_val):
                logging.warning("Calibrated value out of range")

        return round(calibrated, 3)

    def _polynomial_calibration(self, value):
        """Kalibrasi polinomial: y = a*x² + b*x + c"""
        params = self.config["parameters"]
        calibrated = params["a"] * (value**2) + params["b"] * value + params["c"]
        return round(calibrated, 3)

    @staticmethod
    def auto_calibrate(sensor_type, raw_values, reference_values):
        """Auto-kalibrasi menggunakan regresi linier"""
        try:
            if len(raw_values) != len(reference_values):
                raise ValueError("Data mismatch")

            x = np.array(raw_values)
            y = np.array(reference_values)

            # Regresi linier: y = a*x + b
            coeffs = np.polyfit(x, y, 1)

            return {
                "type": "linear",
                "parameters": {"gain": float(coeffs[0]), "offset": float(coeffs[1])},
            }
        except Exception as e:
            logging.error(f"Auto-calibration failed: {e}")
            return None
