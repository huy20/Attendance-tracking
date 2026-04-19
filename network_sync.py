import os
import sqlite3
import json
from datetime import datetime
from kivy.network.urlrequest import UrlRequest
from kivy.clock import Clock

class AttendanceSyncer:
    def __init__(self, base_dir, host_url, sync_interval=60.0):
        self.base_dir = base_dir
        self.host_url = host_url
        self.sync_interval = sync_interval
        self.db_path = os.path.join(self.base_dir, 'attendance.db')
        self.event = None
        
        # NEW: Lock to prevent overlapping syncs if the network is slow
        self.syncing = False 
        self.pending_ids = []

    def start_syncing(self):
        """Starts the background loop"""
        if self.event:
            self.event.cancel()
        self.event = Clock.schedule_interval(self.sync_with_host, self.sync_interval)
        print(f"Network Syncer started. Syncing every {self.sync_interval} seconds.")

    def stop_syncing(self):
        """Stops the background loop"""
        if self.event:
            self.event.cancel()
            self.event = None
            print("Network Syncer stopped.")

    def sync_with_host(self, dt):
        """Reads unsynced data and sends it to the desktop."""
        if not os.path.exists(self.db_path) or self.syncing:
            return 
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # --- NEW: Graceful Database Upgrade ---
            # If the 'synced' column doesn't exist yet, this will add it seamlessly!
            try:
                cursor.execute("ALTER TABLE attendance_logs ADD COLUMN synced INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass # Column already exists, safe to move on
            # --------------------------------------
            
            # Select ONLY records that haven't been synced yet (synced = 0)
            # We also grab 'rowid' which is SQLite's hidden internal ID for every row
            cursor.execute("SELECT rowid, person_name, timestamp FROM attendance_logs WHERE synced = 0")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return # Nothing new to sync, stay quiet!

            # Lock the sync process
            self.syncing = True 
            
            # Remember the exact row IDs we are about to send
            self.pending_ids = [row[0] for row in rows]

            # Format the payload for the host
            payload = {"records": [{"person_name": row[1], "timestamp": row[2]} for row in rows]}
            json_payload = json.dumps(payload)
            headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
            
            UrlRequest(
                self.host_url,
                req_body=json_payload,
                req_headers=headers,
                on_success=self.on_success,
                on_error=self.on_error,
                on_failure=self.on_error
            )
            
        except Exception as e:
            print(f"Sync Prep Error: {e}")
            self.syncing = False

    def on_success(self, req, result):
        """Called automatically when the Desktop replies with a success code."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create a string of question marks equal to the number of IDs: (?, ?, ?)
            placeholders = ','.join(['?'] * len(self.pending_ids))
            
            # Update the local database to flag these specific rows as synced
            cursor.execute(f"UPDATE attendance_logs SET synced = 1 WHERE rowid IN ({placeholders})", self.pending_ids)
            
            conn.commit()
            conn.close()
            
            print(f"SYNC SUCCESS: Uploaded {len(self.pending_ids)} new records. Marked as synced locally.")
            
        except Exception as e:
            print(f"Failed to update local sync status: {e}")
            
        finally:
            # Unlock the syncer so it can run again in the future
            self.syncing = False
            self.pending_ids = []

    def on_error(self, req, result):
        """Called if the Desktop is offline or unreachable."""
        print("SYNC FAILED: Could not reach desktop host. Will try again next cycle.")
        # Unlock the syncer, keeping the records as synced = 0 so they try again next time
        self.syncing = False
        self.pending_ids = []