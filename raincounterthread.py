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
        mm_per_pulse=0.5,  # sensor resolution
        realtime_interval=5,  # 5 detik untuk mode realtime
        polling_ms=20,  # polling cepat (20 ms)
        debounce_ms=20,  # waktu debounce
        max_mm_per_min=8.0,  # intensitas maksimum sensor
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

        # Hitung batas intensitas (pulse per interval)
        self.pulses_per_min_max = max_mm_per_min / mm_per_pulse
        self.pulses_per_interval_warn = (
            self.pulses_per_min_max / 60.0
        ) * realtime_interval

        # Counter
        self.running = True
        self.total_count = 0
        self.daily_count = 0
        self.realtime_count = 0
        self.hourly_count = 0

        # State tracking
        self.last_state = False
        self.last_day = datetime.now().day
        self.last_hour = datetime.now().hour
        self.last_realtime = time.time()

        # Log per jam
        self.hourly_log = {}

        # Load count sebelumnya
        self.load_count()

    # ============================================================
    # Helper
    # ============================================================
    def load_count(self):
        try:
            with open(self.save_path, "r") as f:
                data = json.load(f)
                self.total_count = int(data.get("total", 0))
                self.daily_count = int(data.get("daily", 0))
                self.hourly_log = data.get("hourly", {})
        except Exception:
            pass

    def save_count(self):
        try:
            with open(self.save_path, "w") as f:
                json.dump(
                    {
                        "total": self.total_count,
                        "daily": self.daily_count,
                        "hourly": self.hourly_log,
                        "updated": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"[RainCounter] Error saving rain count: {e}")

    # ============================================================
    # Main thread
    # ============================================================
    def run(self):
        print("[RainCounter] Thread started. (active LOW, 0.5 mm/pulse)")

        while self.running:
            now = datetime.now()
            t = time.time()

            # Reset harian setiap tengah malam
            if now.day != self.last_day:
                self.daily_count = 0
                self.hourly_log = {}
                self.last_day = now.day
                self.save_count()
                print("[RainCounter] Reset daily rainfall.")

            # Reset jam baru
            if now.hour != self.last_hour:
                rainfall_mm = self.hourly_count * self.mm_per_pulse
                hour_key = f"{now.strftime('%Y-%m-%dT%H:00:00')}"
                self.hourly_log[hour_key] = round(rainfall_mm, 2)
                self.hourly_count = 0
                self.last_hour = now.hour
                self.save_count()
                print(
                    f"[RainCounter] Hourly log saved: {hour_key} = {rainfall_mm:.2f} mm"
                )

            try:
                raw_state = self.modbusampere.read_digital_inputs(
                    self.sensor, self.port
                )

                if raw_state is not None:
                    # Aktif LOW → invert hasil bacaan
                    state = not raw_state

                    # Deteksi rising edge (OFF → ON / 1 pulse)
                    if state and not self.last_state:
                        # Debounce cepat (konfirmasi sinyal stabil)
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

            # Reset realtime counter tiap interval (5 detik)
            if t - self.last_realtime >= self.realtime_interval:
                # Hitung intensitas
                mm_interval = self.realtime_count * self.mm_per_pulse
                mm_per_min_equiv = (mm_interval / self.realtime_interval) * 60.0

                if mm_per_min_equiv > 8.0:
                    print(
                        f"[RainCounter][WARN] Intensity too high: "
                        f"{mm_per_min_equiv:.2f} mm/min "
                        f"(allowed ≤ 8 mm/min)"
                    )

                # Reset untuk interval berikutnya
                self.realtime_count = 0
                self.last_realtime = t

            time.sleep(self.polling_s)

    # ============================================================
    # Stop thread
    # ============================================================
    def stop(self):
        self.running = False

    # ============================================================
    # Properti hasil
    # ============================================================
    @property
    def rainfall_realtime(self):
        """Curah hujan selama interval realtime (mis. 5 detik)."""
        return round(self.realtime_count * self.mm_per_pulse, 3)

    @property
    def rainfall_hourly(self):
        """Curah hujan jam ini."""
        return round(self.hourly_count * self.mm_per_pulse, 2)

    @property
    def rainfall_daily(self):
        """Total hujan hari ini."""
        return round(self.daily_count * self.mm_per_pulse, 2)

    @property
    def rainfall_total(self):
        """Akumulasi total sepanjang waktu."""
        return round(self.total_count * self.mm_per_pulse, 2)
