# camera_stream.py
import subprocess
import threading
import time
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Makassar")


class CameraStreamThread(threading.Thread):
    def __init__(self, device_location_id, api_key):
        super().__init__()
        self.device_location_id = device_location_id
        self.api_key = api_key
        self.stream_process = None
        self.is_streaming = False
        self.stream_start_time = None
        self.stream_timeout = 300  # 5 menit
        self.lock = threading.Lock()
        self.daemon = True
        self._stop_event = threading.Event()

    def start_stream(self, mode="day"):
        """Mulai streaming dengan mode siang/malam"""
        with self.lock:
            if self.is_streaming:
                print("⚠️ Streaming sudah berjalan, menghentikan yang lama...")
                self._stop_stream_process()

            try:
                if mode == "night":
                    command = [
                        "libcamera-vid",
                        "-t",
                        "0",
                        "--inline",
                        "--framerate",
                        "3",
                        "--width",
                        "240",
                        "--height",
                        "180",
                        "--codec",
                        "h264",
                        "-b",
                        "100000",
                        "--awb",
                        "incandescent",
                        "--awbgains",
                        "1.8,0.9",
                        "--saturation",
                        "0.0",
                        "--brightness",
                        "0.2",
                        "--contrast",
                        "1.2",
                        "--gain",
                        "8",
                        "--denoise",
                        "cdn_off",
                        "-o",
                        "-",
                    ]
                else:  # day mode
                    command = [
                        "libcamera-vid",
                        "-t",
                        "0",
                        "--inline",
                        "--framerate",
                        "3",
                        "--width",
                        "240",
                        "--height",
                        "180",
                        "--codec",
                        "h264",
                        "-b",
                        "100000",
                        "-o",
                        "-",
                    ]

                ffmpeg_command = [
                    "ffmpeg",
                    "-re",
                    "-i",
                    "-",
                    "-c",
                    "copy",
                    "-f",
                    "rtsp",
                    f"rtsp://pi:rahasia@202.10.35.221:8554/rpi_cam",
                ]

                print(f"🎥 Memulai streaming mode {mode}")

                # Start libcamera-vid process
                libcamera_process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                # Start ffmpeg process dengan input dari libcamera
                ffmpeg_process = subprocess.Popen(
                    ffmpeg_command,
                    stdin=libcamera_process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.stream_process = {
                    "libcamera": libcamera_process,
                    "ffmpeg": ffmpeg_process,
                }

                self.is_streaming = True
                self.stream_start_time = time.time()
                print("✅ Streaming berhasil dimulai")
                return True

            except Exception as e:
                print(f"❌ Error mulai streaming: {e}")
                self._stop_stream_process()
                return False

    def _stop_stream_process(self):
        """Hentikan process streaming secara aman"""
        if self.stream_process:
            try:
                # Hentikan libcamera process
                if self.stream_process["libcamera"]:
                    self.stream_process["libcamera"].terminate()
                    try:
                        self.stream_process["libcamera"].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.stream_process["libcamera"].kill()
                        self.stream_process["libcamera"].wait()

                # Hentikan ffmpeg process
                if self.stream_process["ffmpeg"]:
                    self.stream_process["ffmpeg"].terminate()
                    try:
                        self.stream_process["ffmpeg"].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.stream_process["ffmpeg"].kill()
                        self.stream_process["ffmpeg"].wait()

            except Exception as e:
                print(f"Warning saat menghentikan process: {e}")
            finally:
                self.stream_process = None
                self.is_streaming = False
                self.stream_start_time = None

    def stop_stream(self):
        """Hentikan streaming"""
        with self.lock:
            if self.is_streaming:
                print("🛑 Menghentikan streaming...")
                self._stop_stream_process()
                print("✅ Streaming dihentikan")
                return True
            return False

    def _get_camera_mode(self):
        """Tentukan mode kamera berdasarkan waktu"""
        current_hour = datetime.now(TZ).hour
        return "night" if 18 <= current_hour or current_hour < 6 else "day"

    def take_photo(self):
        """Ambil foto dengan resolusi 1080p dan preset siang/malam"""
        with self.lock:
            # Hentikan streaming jika sedang berjalan
            was_streaming = self.is_streaming
            if was_streaming:
                self.stop_stream()
                time.sleep(2)  # Beri waktu untuk cleanup

            try:
                # Tentukan mode
                mode = self._get_camera_mode()
                timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
                photo_filename = f"/tmp/photo_{self.device_location_id}_{timestamp}.jpg"

                print(
                    f"📸 Mengambil foto mode {mode} dengan resolusi 1080p: {photo_filename}"
                )

                # Base command untuk resolusi 1080p
                photo_command = [
                    "libcamera-jpeg",
                    "-o",
                    photo_filename,
                    "--width",
                    "1920",  # Lebar 1920 pixel
                    "--height",
                    "1080",  # Tinggi 1080 pixel
                    "--quality",
                    "95",  # Kualitas tinggi
                    "--timeout",
                    "5000",  # Timeout 5 detik
                    "--nopreview",  # Nonaktifkan preview
                ]

                # Tambahkan preset berdasarkan mode
                if mode == "night":
                    # PRESET MALAM - Sama seperti streaming malam tapi untuk foto
                    photo_command.extend(
                        [
                            "--awb",
                            "incandescent",
                            "--awbgains",
                            "1.8,0.9",
                            "--saturation",
                            "0.0",
                            "--brightness",
                            "0.2",
                            "--contrast",
                            "1.2",
                            "--gain",
                            "8",
                            "--denoise",
                            "cdn_off",
                            "--shutter",
                            "20000000",  # Shutter 20ms untuk foto (bukan streaming)
                            "--ev",
                            "0.0",  # Exposure compensation normal
                            "--metering",
                            "centre",  # Centre metering
                        ]
                    )
                else:
                    # PRESET SIANG - Untuk foto
                    photo_command.extend(
                        [
                            "--awb",
                            "auto",
                            "--brightness",
                            "0.0",
                            "--contrast",
                            "1.0",
                            "--saturation",
                            "1.0",
                            "--sharpness",
                            "1.0",
                            "--gain",
                            "1.0",
                            "--ev",
                            "0.0",
                            "--metering",
                            "centre",
                            "--shutter",
                            "1000000",  # Shutter 1ms untuk siang
                        ]
                    )

                print(f"🔧 Command foto {mode}: {' '.join(photo_command)}")

                result = subprocess.run(
                    photo_command, capture_output=True, text=True, timeout=30
                )

                if result.returncode != 0:
                    print(f"❌ Error mengambil foto {mode}: {result.stderr}")
                    return self._take_photo_fallback(
                        photo_filename, was_streaming, mode
                    )

                if not os.path.exists(photo_filename):
                    print("❌ File foto tidak terbentuk")
                    return self._take_photo_fallback(
                        photo_filename, was_streaming, mode
                    )

                # Cek ukuran file untuk memastikan foto berhasil
                file_size = os.path.getsize(photo_filename)
                if file_size < 1024:  # Jika file < 1KB, kemungkinan gagal
                    print(
                        f"❌ File foto terlalu kecil ({file_size} bytes), kemungkinan gagal"
                    )
                    return self._take_photo_fallback(
                        photo_filename, was_streaming, mode
                    )

                print(f"✅ Foto {mode} berhasil diambil, ukuran: {file_size} bytes")

                # Kirim foto ke API
                return self._send_photo_to_api(photo_filename, timestamp)

            except subprocess.TimeoutExpired:
                print("❌ Timeout mengambil foto")
                return False
            except Exception as e:
                print(f"❌ Error mengambil foto: {e}")
                return False
            finally:
                # Jika sebelumnya streaming, mulai kembali
                if was_streaming:
                    time.sleep(1)
                    mode = self._get_camera_mode()
                    self.start_stream(mode)

    def _take_photo_fallback(self, photo_filename, was_streaming, mode):
        """Fallback method dengan preset siang/malam yang disederhanakan"""
        try:
            print(f"🔄 Mencoba fallback method mode {mode}...")

            # Base fallback command
            fallback_command = [
                "libcamera-jpeg",
                "-o",
                photo_filename,
                "--width",
                "1920",
                "--height",
                "1080",
                "--quality",
                "90",
                "--timeout",
                "3000",
                "--nopreview",
            ]

            # Tambahkan preset sederhana berdasarkan mode
            if mode == "night":
                # FALLBACK MALAM - Sama seperti streaming
                fallback_command.extend(
                    [
                        "--awb",
                        "incandescent",
                        "--awbgains",
                        "1.8,0.9",
                        "--saturation",
                        "0.0",
                        "--brightness",
                        "0.2",
                        "--contrast",
                        "1.2",
                        "--gain",
                        "4",  # Gain sedikit dikurangi untuk safety
                        "--denoise",
                        "cdn_off",
                    ]
                )
            else:
                # FALLBACK SIANG
                fallback_command.extend(
                    ["--awb", "auto", "--brightness", "0.0", "--contrast", "1.0"]
                )

            result = subprocess.run(
                fallback_command, capture_output=True, text=True, timeout=20
            )

            if result.returncode == 0 and os.path.exists(photo_filename):
                file_size = os.path.getsize(photo_filename)
                print(f"✅ Foto fallback {mode} berhasil, ukuran: {file_size} bytes")

                # Kirim ke API
                timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
                success = self._send_photo_to_api(photo_filename, timestamp)

                # Cleanup
                try:
                    os.remove(photo_filename)
                except:
                    pass

                return success
            else:
                print("❌ Fallback method juga gagal")
                return False

        except Exception as e:
            print(f"❌ Error di fallback method: {e}")
            return False

    def _send_photo_to_api(self, photo_filename, timestamp):
        """Helper method untuk mengirim foto ke API"""
        try:
            print("📤 Mengirim foto ke API...")
            with open(photo_filename, "rb") as photo_file:
                data = {"device_location_id": self.device_location_id}
                files = {
                    "photo": (
                        f"photo_{self.device_location_id}_{timestamp}.jpg",
                        photo_file,
                        "image/jpeg",
                    )
                }
                headers = {"X-API-KEY": self.api_key}

                response = requests.post(
                    "https://telemetry-adaro.id/api/key/device_photo/store",
                    data=data,
                    files=files,
                    headers=headers,
                    verify=False,
                    timeout=30,
                )

                if response.status_code == 200:
                    print("✅ Foto berhasil dikirim ke API")
                    return True
                else:
                    print(
                        f"❌ Gagal kirim foto: {response.status_code} {response.text}"
                    )
                    return False

        except Exception as e:
            print(f"❌ Error mengirim foto ke API: {e}")
            return False
        finally:
            # Hapus file temporary
            try:
                os.remove(photo_filename)
                print("🗑️ File temporary dihapus")
            except Exception as e:
                print(f"⚠️ Gagal hapus file temporary: {e}")

    def check_timeout(self):
        """Cek apakah streaming sudah melebihi timeout"""
        with self.lock:
            if self.is_streaming and self.stream_start_time:
                elapsed = time.time() - self.stream_start_time
                if elapsed > self.stream_timeout:
                    print("⏰ Streaming timeout, menghentikan...")
                    self.stop_stream()
                    return True
            return False

    def is_process_running(self):
        """Cek apakah process streaming masih berjalan"""
        with self.lock:
            if not self.stream_process or not self.is_streaming:
                return False

            # Cek status libcamera process
            libcamera_running = (
                self.stream_process["libcamera"]
                and self.stream_process["libcamera"].poll() is None
            )

            # Cek status ffmpeg process
            ffmpeg_running = (
                self.stream_process["ffmpeg"]
                and self.stream_process["ffmpeg"].poll() is None
            )

            # Jika salah satu process mati, anggap streaming berhenti
            if not libcamera_running or not ffmpeg_running:
                print("⚠️ Process streaming terdeteksi mati")
                self.is_streaming = False
                self.stream_start_time = None
                return False

            return True

    def run(self):
        """Thread utama untuk monitoring timeout dan process health"""
        while not self._stop_event.is_set():
            try:
                # Cek timeout
                self.check_timeout()

                # Cek health process streaming
                if self.is_streaming:
                    if not self.is_process_running():
                        print("🔄 Process streaming tidak berjalan, reset status...")
                        self.is_streaming = False
                        self.stream_start_time = None

            except Exception as e:
                print(f"⚠️ Error di camera monitoring thread: {e}")

            time.sleep(10)  # Cek setiap 10 detik

    def stop(self):
        """Hentikan thread"""
        self._stop_event.set()
        self.stop_stream()
