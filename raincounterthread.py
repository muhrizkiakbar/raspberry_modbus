import threading
import time
import json
from datetime import datetime


class RainCounterThread(threading.Thread):
    """
    Thread penghitung curah hujan berbasis sensor tipping bucket (reed switch).
    Kompatibel dengan Wellpro WP9038ADAM (input aktif LOW).
    """

    def __init__(
        self,
        modbusampere,
        sensor,
        port,
        save_path="/home/ftp/modbus/rain_counter.json",
        mm_per_pulse=0.2,  # resolusi sensor (0.5 mm/pulse)
        realtime_interval=5,  # interval realtime (detik)
        polling_ms=20,  # polling cepat (20 ms)
        debounce_ms=20,  # waktu debounce (20 ms)
        max_mm_per_min=8.0,  # batas intensitas maksimum sensor
    ):
        super().__init__(daemon=True)
        self.modbusampere = modbusampere
        self.sensor = sensor
        self.port = port
        self.mm_per_pulse = mm_per_pulse
        self.save_path = save_path
        self.realtime_interval = realtime_interval
        self.polling_s = polling_ms / 1000.0
        self.debounce_s = debounce_ms / 1000.0

        # batas intensitas
        self.pulses_per_min_max = max_mm_per_min / mm_per_pulse

        # Counter
        self.running = True
        self.total_count = 0
        self.daily_count = 0
        self.realtime_count = 0
        self.hourly_count = 0

        # Tracking waktu
        self.last_state = False
        self.last_day = datetime.now().day
        self.last_hour = datetime.now().hour
        self.last_realtime = time.time()

        # Load data sebelumnya
        self.load_count()

    # ============================================================
    # Helper
    # ============================================================
    def load_count(self):
        try:
            with open(self.save_path, "r") as f:
                data = json.load(f)
                self.total_count = int(data.get("total", 0))
                self.daily_count = int(data.get("daily_count", 0))
                self.hourly_count = int(data.get("hourly_count", 0))
                self.last_hour = data.get("hour", self.last_hour)
        except Exception:
            pass

    def save_count(self):
        try:
            with open(self.save_path, "w") as f:
                json.dump(
                    {
                        "total": self.total_count,
                        "daily_count": self.daily_count,
                        "daily_mm": round(self.daily_count * self.mm_per_pulse, 2),
                        "hourly_count": self.hourly_count,
                        "hourly_mm": round(self.hourly_count * self.mm_per_pulse, 2),
                        "hour": self.last_hour,
                        "updated": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"[RainCounter] Error saving rain count: {e}")

    # ============================================================
    # Main Thread
    # ============================================================
    def run(self):
        print("[RainCounter] Thread started. (active LOW, 0.5 mm/pulse)")

        while self.running:
            now = datetime.now()
            t = time.time()

            # Reset harian setiap tengah malam
            if now.day != self.last_day:
                self.daily_count = 0
                self.hourly_count = 0
                self.last_day = now.day
                self.last_hour = now.hour
                self.save_count()
                print("[RainCounter] Reset daily rainfall.")

            # Reset saat masuk jam baru
            if now.hour != self.last_hour:
                print(
                    f"[RainCounter] Hourly reset. Previous hour total: "
                    f"{self.hourly_count * self.mm_per_pulse:.2f} mm"
                )
                self.hourly_count = 0
                self.last_hour = now.hour
                self.save_count()

            try:
                raw_state = self.modbusampere.read_digital_inputs(
                    self.sensor, self.port
                )

                if raw_state is not None:
                    # Aktif LOW → invert hasil bacaan
                    state = not raw_state

                    # Deteksi rising edge (OFF → ON / 1 pulse)
                    if state and not self.last_state:
                        # Debounce cepat
                        time.sleep(self.debounce_s)
                        confirm = not self.modbusampere.read_digital_inputs(
                            self.sensor, self.port
                        )

                        if confirm:
                            self.total_count += 1
                            self.daily_count += 1
                            self.realtime_count += 1
                            self.hourly_count += 1
                            self.save_count()
                            print(
                                f"[RainCounter] Pulse detected. total={self.total_count}"
                            )

                    self.last_state = state

            except Exception as e:
                print(f"[RainCounter] Read error: {e}")

            # Interval realtime reset
            if t - self.last_realtime >= self.realtime_interval:
                mm_interval = self.realtime_count * self.mm_per_pulse
                mm_per_min_equiv = (mm_interval / self.realtime_interval) * 60.0

                if mm_per_min_equiv > 8.0:
                    print(
                        f"[RainCounter][WARN] Intensity too high: "
                        f"{mm_per_min_equiv:.2f} mm/min (allowed ≤ 8 mm/min)"
                    )

                # Reset untuk interval berikutnya
                self.realtime_count = 0
                self.last_realtime = t

            time.sleep(self.polling_s)

    # ============================================================
    # Stop Thread
    # ============================================================
    def stop(self):
        self.running = False

    # ============================================================
    # Property hasil
    # ============================================================
    @property
    def rainfall_realtime(self):
        return round(self.realtime_count * self.mm_per_pulse, 3)

    @property
    def rainfall_hourly(self):
        return round(self.hourly_count * self.mm_per_pulse, 2)

    @property
    def rainfall_daily(self):
        return round(self.daily_count * self.mm_per_pulse, 2)

    @property
    def rainfall_total(self):
        return round(self.total_count * self.mm_per_pulse, 2)
