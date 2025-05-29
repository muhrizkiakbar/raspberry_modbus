import sqlite3
import zlib
import json
from datetime import datetime, timedelta
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import logging


class SecureDatabase:
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cipher = AES.new(
            pad(self.config["database"]["encryption_key"].encode(), 32), AES.MODE_CBC
        )

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.config["database"]["path"])
            self._enable_encryption()
            self._initialize_tables()
            return True
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            return False

    def _enable_encryption(self):
        self.conn.execute(f"PRAGMA key='{self.config['database']['encryption_key']}'")
        self.conn.execute("PRAGMA cipher_compatibility=4")

    def _initialize_tables(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS sensor_data
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           timestamp DATETIME,
                           sensor TEXT,
                           value BLOB)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS alarms
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           timestamp DATETIME,
                           sensor TEXT,
                           message BLOB)""")

    def insert_batch(self, data):
        try:
            compressed = zlib.compress(json.dumps(data).encode())
            encrypted = self.cipher.encrypt(pad(compressed, AES.block_size))

            self.conn.executemany(
                "INSERT INTO sensor_data (timestamp, sensor, value) VALUES (?,?,?)",
                [(datetime.now(), k, encrypted) for k, v in data.items()],
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"Batch insert failed: {e}")

    def cleanup_old_data(self):
        try:
            cutoff = datetime.now() - timedelta(
                days=self.config["database"]["retention_days"]
            )
            self.conn.execute("DELETE FROM sensor_data WHERE timestamp < ?", (cutoff,))
            self.conn.execute("VACUUM")
            return True
        except Exception as e:
            logging.error(f"Data cleanup failed: {e}")
            return False

    def get_recent_data(self, limit=100):
        try:
            cur = self.conn.execute(
                "SELECT timestamp, sensor, value FROM sensor_data ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            return [self._decrypt_row(row) for row in cur.fetchall()]
        except Exception as e:
            logging.error(f"Data retrieval failed: {e}")
            return []

    def _decrypt_row(self, row):
        try:
            decrypted = unpad(self.cipher.decrypt(row[2]), AES.block_size)
            decompressed = zlib.decompress(decrypted)
            return (row[0], row[1], json.loads(decompressed))
        except Exception as e:
            logging.error(f"Decryption failed: {e}")
            return (row[0], row[1], "ERROR")
