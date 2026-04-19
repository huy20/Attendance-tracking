import cv2
import numpy as np
import os
import sqlite3
import time
from datetime import datetime

class FaceEmbedder:
    def __init__(self, model_filename="MobileFaceNet.onnx"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, model_filename)
        
        # Load the ONNX model
        self.net = cv2.dnn.readNetFromONNX(model_path)
        
        # Recognition variables
        self.known_names = []
        self.known_embeddings = []
        self.threshold = 0.75
        
        # Will be set when loading
        self.log_db_path = None 

    def load_database(self, base_dir):
        """Loads embeddings from faces.db and creates attendance.db"""
        faces_db_path = os.path.join(base_dir, "faces.db")
        self.log_db_path = os.path.join(base_dir, "attendance.db")
        
        self._setup_log_db()
        
        if not os.path.exists(faces_db_path):
            print("No faces database found yet!")
            return
            
        conn = sqlite3.connect(faces_db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT person_name, embedding FROM user_embeddings")
            rows = cursor.fetchall()
            
            self.known_names = []
            self.known_embeddings = []
            
            for row in rows:
                name = row[0]
                # Convert the raw BLOB bytes back into a NumPy array
                embedding = np.frombuffer(row[1], dtype=np.float32)
                
                self.known_names.append(name)
                self.known_embeddings.append(embedding)
                
            print(f"Loaded {len(self.known_names)} embeddings into memory.")
        except sqlite3.OperationalError:
            print("Database exists, but no user table found.")
        finally:
            conn.close()

    def get_embedding(self, cropped_face_bgr):
        resized = cv2.resize(cropped_face_bgr, (112, 112))
        blob = cv2.dnn.blobFromImage(
            resized, scalefactor=1.0, size=(112, 112), 
            mean=(0, 0, 0), swapRB=True
        )
        self.net.setInput(blob)
        return self.net.forward()[0]

    def cosine_similarity(self, a, b):
        """Calculates how closely two vectors match (1.0 is perfect match, -1.0 is opposite)"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def recognize(self, cropped_face_bgr):
        """Returns the best matching name and its confidence score"""
        if not self.known_embeddings:
            return "Unknown", 0.0
            
        query_emb = self.get_embedding(cropped_face_bgr)
        
        best_match_name = "Unknown"
        best_sim = -1.0
        
        for name, known_emb in zip(self.known_names, self.known_embeddings):
            sim = self.cosine_similarity(query_emb, known_emb)
            if sim > best_sim:
                best_sim = sim
                best_match_name = name
                
        if best_sim >= self.threshold:
            return best_match_name, best_sim
        return "Unknown", best_sim

    def _setup_log_db(self):
        """Creates the attendance logging database"""
        conn = sqlite3.connect(self.log_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_name TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def log_recognition(self, name):
        """Saves a record of the person being recognized"""
        if not self.log_db_path: return
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.log_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO attendance_logs (person_name, timestamp) VALUES (?, ?)", 
            (name, now)
        )
        conn.commit()
        conn.close()
        print(f"Logged {name} at {now}")