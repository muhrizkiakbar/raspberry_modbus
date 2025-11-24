# camera_stream.py
import subprocess
import threading
import time
import requests
import os
import json
import paho.mqtt.client as mqtt
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Makassar")


class CameraStreamThread(threading.Thread):
    def __init__(
        self, device_location_id, api_key, mqtt_config, mqtt_username, mqtt_password
    ):
        super().__init__()
        self.device_location_id = device_location_id
        self.api_key = api_key
        self.mqtt_config = mqtt_config
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password

        self.stream_process = None
        self.is_streaming = False
        self.stream_start_time = None
        self.stream_timeout = 300  # 5 menit
        self.lock = threading.Lock()
        self.daemon = True
        self._stop_event = threading.Event()

        # Setup MQTT topics - menggunakan base_topic
        self.command_topic = f"{mqtt_config['base_topic']}/camera/command"
        self.status_topic = f"{mqtt_config['base_topic']}/camera"

        # Buat MQTT client terpisah untuk camera
        self.mqtt_client = self._init_mqtt_client()

        print(f"🎥 Camera thread initialized with topics:")
        print(f"   Command: {self.command_topic}")
        print(f"   Status: {self.status_topic}")

    def _init_mqtt_client(self):
        """Inisialisasi MQTT client terpisah untuk camera"""
        try:
            client_id = f"{self.mqtt_config['client_id']}_camera"
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
            client.username_pw_set(self.mqtt_username, self.mqtt_password)
            client.on_connect = self._on_mqtt_connect
            client.on_message = self._on_mqtt_message

            # Connect ke broker
            client.connect(self.mqtt_config["broker"], self.mqtt_config["port"])
            client.loop_start()

            print(
                f"✅ Camera MQTT client connected to {self.mqtt_config['broker']}:{self.mqtt_config['port']}"
            )
            return client

        except Exception as e:
            print(f"❌ Gagal inisialisasi MQTT client camera: {e}")
            return None

    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """Callback ketika MQTT client camera terhubung"""
        if reason_code == 0:
            print("✅ Camera MQTT client connected successfully")
            # Subscribe hanya ke topic camera command
            client.subscribe(self.command_topic, qos=1)
            print(f"📡 Camera subscribed exclusively to: {self.command_topic}")

            # Publish status online
            self._publish_camera_status("online")
        else:
            print(f"❌ Camera MQTT connection failed: {reason_code}")

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages khusus untuk camera"""
        try:
            payload = msg.payload.decode().strip().lower()
            print(f"📨 Camera command diterima: '{payload}' dari topic: {msg.topic}")

            if payload == "stream":
                self._handle_stream_command()
            elif payload == "take":
                self._handle_take_photo_command()
            elif payload == "stop":
                self._handle_stop_command()
            else:
                print(f"⚠️ Command camera tidak dikenali: {payload}")

        except Exception as e:
            print(f"❌ Error handling MQTT camera message: {e}")

    def _handle_stream_command(self):
        """Handle command stream dari MQTT"""
        print("🎥 Received stream command via MQTT")
        if self.is_streaming:
            print("⚠️ Streaming sudah aktif")
            self._publish_camera_status("streaming_active")
        else:
            mode = self._get_camera_mode()
            if self.start_stream(mode):
                self._publish_camera_status("streaming_started")
            else:
                self._publish_camera_status("streaming_failed")

    def _handle_take_photo_command(self):
        """Handle command take photo dari MQTT"""
        print("📸 Received take photo command via MQTT")
        if self.take_photo():
            self._publish_camera_status("photo_success")
        else:
            self._publish_camera_status("photo_failed_take_photo_failed")

    def _handle_stop_command(self):
        """Handle command stop dari MQTT"""
        print("🛑 Received stop command via MQTT")
        if self.stop_stream():
            self._publish_camera_status("streaming_stopped")
        else:
            self._publish_camera_status("streaming_not_active")

    def _publish_camera_status(self, status):
        """Publish status camera ke MQTT"""
        try:
            payload = {
                "device_location_id": self.device_location_id,
                "camera": status,
                "timestamp": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
                "is_streaming": self.is_streaming,
                "streaming_since": self.stream_start_time,
            }

            if self.mqtt_client:
                self.mqtt_client.publish(self.status_topic, json.dumps(payload), qos=1)
                print(f"📤 Camera status published: {status}")

        except Exception as e:
            print(f"❌ Gagal publish camera status: {e}")

    def _publish_heartbeat(self):
        """Publish heartbeat status camera"""
        try:
            status = "streaming" if self.is_streaming else "online"
            payload = {
                "device_location_id": self.device_location_id,
                "camera": status,
                "timestamp": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
                "streaming_time": time.time() - self.stream_start_time
                if self.is_streaming
                else 0,
            }

            if self.mqtt_client:
                self.mqtt_client.publish(self.status_topic, json.dumps(payload), qos=1)

        except Exception as e:
            print(f"❌ Gagal publish camera heartbeat: {e}")

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

                # Publish status
                self._publish_camera_status("streaming_started")
                return True

            except Exception as e:
                print(f"❌ Error mulai streaming: {e}")
                self._stop_stream_process()
                self._publish_camera_status("streaming_failed")
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
                self._publish_camera_status("streaming_stopped")
                return True
            return False

    def _get_camera_mode(self):
        """Tentukan mode kamera berdasarkan waktu"""
        current_hour = datetime.now(TZ).hour
        return "night" if 18 <= current_hour or current_hour < 6 else "day"

    def take_photo(self):
        """Ambil foto dengan resolusi 1080p menggunakan libcamera-still"""
        with self.lock:
            # Hentikan streaming jika sedang berjalan
            was_streaming = self.is_streaming
            if was_streaming:
                self.stop_stream()
                time.sleep(2)  # Beri waktu untuk cleanup

            try:
                # Tentukan mode
                self._publish_camera_status("photo_requested")
                mode = self._get_camera_mode()
                timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
                photo_filename = f"/tmp/photo_{self.device_location_id}_{timestamp}.jpg"

                print(
                    f"📸 Mengambil foto mode {mode} dengan libcamera-still: {photo_filename}"
                )

                # Base command untuk libcamera-still
                photo_command = []

                # Tambahkan preset berdasarkan mode
                if mode == "night":
                    photo_command = [
                        "libcamera-still",
                        "-o",
                        photo_filename,
                        "--width",
                        "1920",
                        "--height",
                        "1080",
                        "--timeout",
                        "10000",  # 5 detik
                        "--nopreview",
                        "--quality",
                        "98",
                        "--awb",
                        "tungsten",
                    ]

                else:  # day mode
                    photo_command = [
                        "libcamera-still",
                        "-o",
                        photo_filename,
                        "--width",
                        "1920",
                        "--height",
                        "1080",
                        "--timeout",
                        "10000",  # 5 detik
                        "--nopreview",
                        "--quality",
                        "98",
                    ]

                print(f"🔧 Command foto {mode}: {' '.join(photo_command)}")

                result = subprocess.run(
                    photo_command, capture_output=True, text=True, timeout=30
                )

                if result.returncode != 0:
                    print(f"❌ Error mengambil foto {mode}: {result.stderr}")
                    self._publish_camera_status(
                        "photo_failed_return_code" + result.stderr
                    )
                    return False

                if not os.path.exists(photo_filename):
                    print("❌ File foto tidak terbentuk")
                    self._publish_camera_status("photo_failed_os_path_exist")
                    return False

                file_size = os.path.getsize(photo_filename)
                if file_size < 1024:
                    print(
                        f"❌ File foto terlalu kecil ({file_size} bytes), kemungkinan gagal"
                    )
                    self._publish_camera_status("photo_failed_failed_take_photo")
                    return False

                print(f"✅ Foto {mode} berhasil diambil, ukuran: {file_size} bytes")

                success = self._send_photo_to_api(photo_filename, timestamp)

                if success:
                    self._publish_camera_status("photo_success")
                else:
                    self._publish_camera_status("photo_failed_send_post_api")

                return success

            except subprocess.TimeoutExpired:
                print("❌ Timeout mengambil foto")
                self._publish_camera_status("photo_timeout")
                return False
            except Exception as e:
                print(f"❌ Error mengambil foto: {e}")
                self._publish_camera_status("photo_error")
                return False
            finally:
                # Jika sebelumnya streaming, mulai kembali
                if was_streaming:
                    time.sleep(1)
                    mode = self._get_camera_mode()
                    self.start_stream(mode)

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
        last_heartbeat = 0
        heartbeat_interval = 30  # 30 detik

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
                        self._publish_camera_status("streaming_crashed")

                # Publish heartbeat setiap interval
                current_time = time.time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    self._publish_heartbeat()
                    last_heartbeat = current_time

            except Exception as e:
                print(f"⚠️ Error di camera monitoring thread: {e}")

            time.sleep(10)  # Cek setiap 10 detik

    def stop(self):
        """Hentikan thread"""
        self._stop_event.set()
        self.stop_stream()

        # Hentikan MQTT client
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                print("✅ Camera MQTT client stopped")
            except Exception as e:
                print(f"⚠️ Error stopping camera MQTT client: {e}")

        self._publish_camera_status("offline")
        print("✅ Camera thread stopped")
