import os
import sqlite3
import json
import threading
import time
import base64
import requests
import shutil

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# ── Device Identity ───────────────────────────────────────────────────────────
DEVICE_ID = "android_device_1"

def _ensure_keys(keys_dir):
    os.makedirs(keys_dir, exist_ok=True)
    priv_path = os.path.join(keys_dir, "private_key.pem")
    pub_path = os.path.join(keys_dir, "public_key.pem")

    if not os.path.exists(priv_path) or not os.path.exists(pub_path):
        print(f"Generating new RSA keys for {DEVICE_ID}...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        with open(priv_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        public_key = private_key.public_key()
        with open(pub_path, "wb") as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
        print("Keys generated successfully.")
    
    with open(priv_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

class AttendanceSyncer:
    def __init__(self, base_dir, host_url, sync_interval=60.0):
        self.base_dir = base_dir
        
        # Keys setup
        self.keys_dir = os.path.join(base_dir, "keys", DEVICE_ID)
        self._private_key = _ensure_keys(self.keys_dir)
        
        self.db_path = os.path.join(base_dir, 'attendance.db')
        self.faces_db_path = os.path.join(base_dir, 'faces.db')
        
        self.sync_interval = sync_interval
        self.faces_sync_interval = 5 # 5 seconds
        
        self.running = False
        self.thread = None
        self.faces_thread = None

        # Fix URL formatting if user inputted full sync URL
        if "/sync" in host_url:
            self.gateway_url = host_url.replace("/sync", "").rstrip("/")
        else:
            self.gateway_url = host_url.rstrip("/")
            
        self.attendance_url   = f"{self.gateway_url}/sync"
        self.faces_version_url = f"{self.gateway_url}/faces/version"
        self.faces_download_url = f"{self.gateway_url}/faces/download"
        self.faces_upload_url  = f"{self.gateway_url}/faces/upload"
        self.faces_delete_url  = f"{self.gateway_url}/faces/delete"
        
        self.verify = False 
        self.syncing = False

        # Expose the event attribute so UI thinks we're active
        self.event = None

    def reset_keys(self):
        """Deletes existing keys and generates a new pair."""
        priv_path = os.path.join(self.keys_dir, "private_key.pem")
        pub_path = os.path.join(self.keys_dir, "public_key.pem")
        if os.path.exists(priv_path):
            os.remove(priv_path)
        if os.path.exists(pub_path):
            os.remove(pub_path)
        self._private_key = _ensure_keys(self.keys_dir)

    def export_public_key(self, export_dir):
        """Copies the public key to a public Android directory like Download"""
        pub_path = os.path.join(self.keys_dir, "public_key.pem")
        if os.path.exists(pub_path):
            try:
                os.makedirs(export_dir, exist_ok=True)
                dest = os.path.join(export_dir, f"{DEVICE_ID}.pem")
                shutil.copy2(pub_path, dest)
                return True, dest
            except Exception as e:
                return False, str(e)
        return False, "Public key not found."

    def make_headers(self, body_str: str) -> dict:
        timestamp = str(int(time.time()))
        message = f"{DEVICE_ID}.{timestamp}.{body_str}".encode()

        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

        return {
            "Content-Type": "application/json",
            "X-Device-ID":  DEVICE_ID,
            "X-Timestamp":  timestamp,
            "X-Signature":  base64.b64encode(signature).decode(),
        }

    def signed_post(self, url: str, payload: dict) -> requests.Response:
        body_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        return requests.post(
            url,
            data=body_str,
            headers=self.make_headers(body_str),
            verify=self.verify,
            timeout=10,
        )

    def signed_get(self, url: str) -> requests.Response:
        return requests.get(
            url,
            headers=self.make_headers(""),
            verify=self.verify,
            timeout=10,
        )

    def start_syncing(self):
        if self.running:
            return
        self.running = True
        self.event = True # Dummy truthy value so UI knows it's active

        self.thread = threading.Thread(target=self._attendance_loop, daemon=True)
        self.thread.start()

        self.faces_thread = threading.Thread(target=self._faces_loop, daemon=True)
        self.faces_thread.start()
        print(f"Network Syncer started: {self.gateway_url}")

    def stop_syncing(self):
        self.running = False
        self.event = None
        print("Network Syncer stopped.")

    def sync_with_host(self, dt):
        # Triggered manually from UI
        threading.Thread(target=self._sync_attendance, daemon=True).start()
        threading.Thread(target=self._push_new_embeddings, daemon=True).start()
        threading.Thread(target=self._pull_faces_if_outdated, daemon=True).start()

    def _attendance_loop(self):
        while self.running:
            self._sync_attendance()
            for _ in range(int(self.sync_interval)):
                if not self.running: break
                time.sleep(1)

    def _faces_loop(self):
        self._push_new_embeddings()
        self._pull_faces_if_outdated()
        while self.running:
            for _ in range(self.faces_sync_interval):
                if not self.running: break
                time.sleep(1)
            if not self.running: break
            self._push_new_embeddings()
            self._pull_faces_if_outdated()

    def _sync_attendance(self):
        if not os.path.exists(self.db_path) or self.syncing:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                try:
                    conn.execute("ALTER TABLE attendance_logs ADD COLUMN synced INTEGER DEFAULT 0")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass
                rows = conn.execute("SELECT rowid, person_name, timestamp FROM attendance_logs WHERE synced = 0").fetchall()

            if not rows:
                return

            self.syncing = True
            pending_ids = [row[0] for row in rows]
            payload = {"records": [{"person_name": row[1], "timestamp": row[2]} for row in rows]}

            response = self.signed_post(self.attendance_url, payload)

            if response.status_code == 200:
                with sqlite3.connect(self.db_path) as conn:
                    placeholders = ','.join(['?'] * len(pending_ids))
                    conn.execute(f"UPDATE attendance_logs SET synced = 1 WHERE rowid IN ({placeholders})", pending_ids)
                    conn.commit()
                print(f"ATTENDANCE SYNC SUCCESS: {len(pending_ids)} records.")
            else:
                print(f"ATTENDANCE SYNC FAILED: {response.text}")
        except Exception as e:
            print(f"Attendance Sync Error: {e}")
        finally:
            self.syncing = False

    def _push_new_embeddings(self):
        if not os.path.exists(self.faces_db_path):
            return
        try:
            with sqlite3.connect(self.faces_db_path) as conn:
                try:
                    conn.execute("ALTER TABLE user_embeddings ADD COLUMN synced INTEGER DEFAULT 0")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass
                rows = conn.execute("SELECT rowid, person_name, embedding FROM user_embeddings WHERE synced = 0").fetchall()

            if not rows:
                return

            pending_ids = [row[0] for row in rows]
            embeddings = [
                {
                    "person_name": row[1],
                    "embedding": base64.b64encode(row[2]).decode()
                }
                for row in rows
            ]

            payload = {"device_id": DEVICE_ID, "embeddings": embeddings}
            response = self.signed_post(self.faces_upload_url, payload)

            if response.status_code == 200:
                with sqlite3.connect(self.faces_db_path) as conn:
                    placeholders = ','.join(['?'] * len(pending_ids))
                    conn.execute(f"UPDATE user_embeddings SET synced = 1 WHERE rowid IN ({placeholders})", pending_ids)
                    conn.commit()
                print(f"FACES PUSH SUCCESS: {len(pending_ids)} embeddings.")
        except Exception as e:
            print(f"Faces Push Error: {e}")

    def _get_local_faces_version(self):
        if not os.path.exists(self.faces_db_path): return 0
        try:
            with sqlite3.connect(self.faces_db_path) as conn:
                row = conn.execute("SELECT version FROM faces_version WHERE id = 1").fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def _update_local_faces_version(self, version: int, updated_at: str):
        with sqlite3.connect(self.faces_db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS faces_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            conn.execute('INSERT OR REPLACE INTO faces_version (id, version, updated_at) VALUES (1, ?, ?)', (version, updated_at))
            conn.commit()

    def _pull_faces_if_outdated(self):
        try:
            response = self.signed_get(self.faces_version_url)
            if response.status_code != 200: return

            data = response.json()
            host_version = data.get("version", 0)
            if host_version <= self._get_local_faces_version(): return

            response = self.signed_get(self.faces_download_url)
            if response.status_code != 200: return

            embeddings = response.json().get("embeddings", [])
            with sqlite3.connect(self.faces_db_path) as conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS user_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_name TEXT, embedding BLOB,
                    device_id TEXT, registered_at TEXT, synced INTEGER DEFAULT 1)''')
                conn.execute("DELETE FROM user_embeddings")
                for emb in embeddings:
                    conn.execute('''INSERT INTO user_embeddings (person_name, embedding, device_id, registered_at, synced)
                                    VALUES (?, ?, ?, ?, 1)''', (
                        emb["person_name"], base64.b64decode(emb["embedding"]),
                        emb.get("device_id", "unknown"), emb.get("registered_at", "")
                    ))
                conn.commit()
            self._update_local_faces_version(host_version, data.get("updated_at", ""))
            print(f"FACES PULL SUCCESS: Version {host_version}.")
        except Exception as e:
            print(f"Faces Pull Error: {e}")

    def push_delete(self, person_name: str):
        payload = {"device_id": DEVICE_ID, "person_name": person_name}
        try:
            threading.Thread(target=self.signed_post, args=(self.faces_delete_url, payload), daemon=True).start()
        except Exception as e:
            print(f"Delete Push Error: {e}")