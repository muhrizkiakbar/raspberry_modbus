import threading
import json
from datetime import datetime
import time


# ============================================================
# RainCounterThread (realtime per 5s, daily, total) -- updated
# Sensor spec:
#  - resolution: 0.5 mm per pulse
#  - output: pulse (reed/tipping bucket)
#  - max intensity allowed: 8 mm/min -> 16 pulses/min
# ============================================================
class RainCounterThread(threading.Thread):
    def __init__(
        self,
        modbusampere,
        sensor,
        port,
        save_path="/home/ftp/modbus/rain_counter.json",
        mm_per_pulse=0.5,  # <- sesuaikan dengan spec sensor
        realtime_interval=5,  # 5 second realtime window
        polling_ms=100,  # polling every 100ms
        max_mm_per_min=8.0,  # spec: 8 mm/min maximum allowed
    ):
        super().__init__(daemon=True)
        self.modbusampere = modbusampere
        self.sensor = sensor
        self.port = port
        self.mm_per_pulse = mm_per_pulse
        self.save_path = save_path
        self.realtime_interval = realtime_interval
        self.polling_s = polling_ms / 1000.0

        # compute thresholds
        # pulses_per_min_max = max_mm_per_min / mm_per_pulse
        self.pulses_per_min_max = max_mm_per_min / self.mm_per_pulse
        # pulses allowed in realtime interval (5s)
        self.pulses_per_interval_max = (
            self.pulses_per_min_max / 60.0
        ) * self.realtime_interval
        # add small tolerance and round up
        self.pulses_per_interval_warn = max(1, int(self.pulses_per_interval_max + 1))

        # Thread state
        self.running = True
        self.total_count = 0
        self.realtime_count = 0
        self.daily_count = 0
        self.last_state = False
        self.last_day = datetime.now().day
        self.last_realtime = time.time()

        # For debounce: require stable edge for confirm_ms
        self.debounce_confirm_ms = 50

        # Load persisted counts
        self.load_count()

    def load_count(self):
        try:
            with open(self.save_path, "r") as f:
                data = json.load(f)
                self.total_count = int(data.get("total", 0))
                self.daily_count = int(data.get("daily", 0))
        except Exception:
            # file mungkin belum ada: fine
            pass

    def save_count(self):
        try:
            with open(self.save_path, "w") as f:
                json.dump(
                    {
                        "total": self.total_count,
                        "daily": self.daily_count,
                        "last_saved": datetime.now().isoformat(),
                    },
                    f,
                )
        except Exception as e:
            print(f"[RainCounter] Error saving rain count: {e}")

    def _confirm_pulse(self):
        """
        Simple debounce: after seeing active (True) state, wait debounce_confirm_ms and re-read.
        Return True if still active.
        """
        try:
            time.sleep(self.debounce_confirm_ms / 1000.0)
            confirm = self.modbusampere.read_digital_inputs(self.sensor, self.port)
            return bool(confirm)
        except Exception:
            return False

    def run(self):
        print(
            "[RainCounter] Thread started. mm_per_pulse={} mm, realtime_interval={}s".format(
                self.mm_per_pulse, self.realtime_interval
            )
        )
        while self.running:
            now = datetime.now()
            current_time = time.time()

            # Reset harian setiap tengah malam (jika hari berganti)
            if now.day != self.last_day:
                self.daily_count = 0
                self.last_day = now.day
                print("[RainCounter] Reset daily rainfall at midnight.")
                self.save_count()

            try:
                state = self.modbusampere.read_digital_inputs(self.sensor, self.port)
                print(
                    "=================================== State ========================"
                )
                print(state)
                print(self.daily_count)
                print(self.total_count)
                print(self.realtime_count)
                if state is not None:
                    # detect rising edge (active True after being False)
                    if state and not self.last_state:
                        # confirm debounce to avoid false bouncing
                        if self._confirm_pulse():
                            self.total_count += 1
                            self.realtime_count += 1
                            self.daily_count += 1
                            self.save_count()
                            print(
                                f"[RainCounter] Pulse detected. total={self.total_count}, realtime_count={self.realtime_count}"
                            )
                        else:
                            # bounce ignored
                            pass
                    self.last_state = state
            except Exception as e:
                print(f"[RainCounter] Read error: {e}")

            # jika realtime interval lewat, kita reset realtime_count (window sliding fixed)
            if current_time - self.last_realtime >= self.realtime_interval:
                # Before reset, we can check intensity and warn if exceeds allowed
                # Compute pulses in last interval (self.realtime_count)
                if self.realtime_count > self.pulses_per_interval_warn:
                    mm_interval = self.realtime_count * self.mm_per_pulse
                    mm_per_min_equiv = (mm_interval / self.realtime_interval) * 60.0
                    print(
                        f"[RainCounter][WARN] High intensity detected: {self.realtime_count} pulses in {self.realtime_interval}s => {mm_interval} mm ({mm_per_min_equiv:.2f} mm/min). Max allowed {self.pulses_per_min_max * self.mm_per_pulse:.2f} mm/min"
                    )
                    # you may choose to cap the reported realtime or send flag; here we still report the measured value but warn.

                # reset realtime count for next window
                self.realtime_count = 0
                self.last_realtime = current_time

            time.sleep(self.polling_s)

    def stop(self):
        self.running = False

    @property
    def rainfall_realtime(self):
        """Hujan per interval realtime (misal 5 detik) in mm."""
        return round(self.realtime_count * self.mm_per_pulse, 3)

    @property
    def rainfall_daily(self):
        return round(self.daily_count * self.mm_per_pulse, 2)

    @property
    def rainfall_total(self):
        return round(self.total_count * self.mm_per_pulse, 2)
