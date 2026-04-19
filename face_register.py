import math
import time
import cv2
import numpy as np
from jnius import autoclass, cast

# Android/ML Kit Java Classes
FaceDetection = autoclass('com.google.mlkit.vision.face.FaceDetection')
FaceDetectorOptions = autoclass('com.google.mlkit.vision.face.FaceDetectorOptions')
InputImage = autoclass('com.google.mlkit.vision.common.InputImage')
FaceDetectorBuilder = autoclass('com.google.mlkit.vision.face.FaceDetectorOptions$Builder')

class FaceRegister:
    def __init__(self):
        # --- Config & Thresholds ---
        self.COOLDOWN = 0.2
        self.RESET_DELAY = 2.0
        self.MAX_SHOTS = 10
        self.STABILITY_THRESHOLD = 20
        
        self.MAX_YAW = 18.0    
        self.MAX_PITCH = 15.0  
        self.MAX_TILT = 5.0   
        self.MIN_FACE_H, self.MAX_FACE_H = 0.35, 0.8

        # --- State Variables ---
        self.last_capture_time = 0
        self.stability_counter = 0
        self.shots_taken = 0
        self.is_locked = False
        self.last_seen_time = time.time()
        self.last_blink_time = time.time()
        self.blink_detected = False

        # --- Initialize ML Kit ---
        builder_instance = FaceDetectorBuilder()

        options = builder_instance \
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST) \
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL) \
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL) \
            .build()

        self.detector = FaceDetection.getClient(options)

    def reset_session(self):
        self.shots_taken = 0
        self.is_locked = False
        self.stability_counter = 0

    def is_bright(self, frame, face, lower_bound=70, uppper_bound=180):
        bounds = face.getBoundingBox()
        x, y = bounds.left, bounds.top
        right, bottom = bounds.right, bounds.bottom

        h_frame, w_frame, _ = frame.shape
        x, y = max(0, x), max(0, y)
        right, bottom = min(w_frame, right), min(h_frame, bottom)

        face_crop = frame[y:bottom, x:right]
        
        if face_crop.size == 0:
            return False, "Face out of bounds"

        gray_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        average_brightness = np.mean(gray_face)

        if average_brightness < lower_bound:
            return False, "Too Dark! Face the light."
        elif average_brightness > uppper_bound:
            return False, "Too Bright! Avoid harsh light."
        
        return True, "Lighting OK"

    def is_not_blurry(self, gray_frame, threshold=80):
        return cv2.Laplacian(gray_frame, cv2.CV_64F).var() > threshold

    def check_liveness(self, face):
        left_eye = face.getLeftEyeOpenProbability()
        right_eye = face.getRightEyeOpenProbability()
        
        l_prob = left_eye if left_eye is not None else 0.0
        r_prob = right_eye if right_eye is not None else 0.0

        if l_prob < 0.4 or r_prob < 0.4:
            self.blink_detected = True
            self.last_blink_time = time.time()

        if time.time() - self.last_blink_time > 10:
            self.blink_detected = False
        return self.blink_detected

    def crop_face_native(self, frame, face_box):
        h, w, _ = frame.shape
        # FIX: Changed to use dictionary brackets
        left, top, right, bottom = face_box["left"], face_box["top"], face_box["right"], face_box["bottom"]
        
        padding = int((right - left) * 0.2)
        x1, y1 = max(0, left - padding), max(0, top - padding)
        x2, y2 = min(w, right + padding), min(h, bottom + padding)
        return frame[y1:y2, x1:x2]
    
    def is_centered(self, face_box, frame_w, frame_h, threshold=0.15):
        # FIX: Changed to use dictionary brackets
        left, top = face_box["left"], face_box["top"]
        right, bottom = face_box["right"], face_box["bottom"]
        
        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        
        norm_cx = cx / frame_w
        norm_cy = cy / frame_h
        
        if abs(norm_cx - 0.5) < threshold and abs(norm_cy - 0.5) < threshold:
            return True, "Face Centered"
            
        return False, "Move to the center"

    def run(self, frame):
        reasons = []
        captured_face = None
        status = "WAITING"

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w, _ = frame.shape
        
        yuv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_YV12)
        pixels = yuv_frame.tobytes()
        
        input_image = InputImage.fromByteArray(pixels, w, h, 0, InputImage.IMAGE_FORMAT_YV12)
        
        task = self.detector.process(input_image)
        while not task.isComplete(): 
            time.sleep(0.001)
        
        if not task.isSuccessful():
            return {"status": "ERROR", "reasons": ["AI Busy"], "progress": 0, "count": self.shots_taken, "max_shots": self.MAX_SHOTS}
            
        faces = task.getResult()

        if faces.isEmpty():
            if time.time() - self.last_seen_time > self.RESET_DELAY:
                self.reset_session()
            return {"status": "NO FACE", "reasons": ["Searching..."], "progress": 0, "count": self.shots_taken, "max_shots": self.MAX_SHOTS}

        face = faces.get(0)
        self.last_seen_time = time.time()

        if self.is_locked:
            return {"status": "COMPLETE", "reasons": ["Step away"], "progress": 1.0, "count": self.shots_taken, "max_shots": self.MAX_SHOTS}

        light_ok, msg = self.is_bright(frame, face)
        if not light_ok: reasons.append(msg)
        if not self.is_not_blurry(gray): reasons.append("Hold still")

        yaw = face.getHeadEulerAngleY() 
        pitch = face.getHeadEulerAngleX() 
        tilt = face.getHeadEulerAngleZ()

        if abs(yaw) > self.MAX_YAW: reasons.append("Look at camera")
        if abs(pitch) > self.MAX_PITCH: reasons.append("Level your head")
        if abs(tilt) > self.MAX_TILT: reasons.append("Straighten head")

        # --- THE FIX: INSTANTLY CONVERT TO PYTHON DICTIONARY ---
        java_box = face.getBoundingBox()
        box = {
            "left": java_box.left,
            "top": java_box.top,
            "right": java_box.right,
            "bottom": java_box.bottom,
            "width": java_box.width(),
            "height": java_box.height()
        }
        # -------------------------------------------------------

        # FIX: Now using dictionary syntax
        face_h_ratio = box["height"] / h
        if face_h_ratio < self.MIN_FACE_H: reasons.append("Too far")
        if face_h_ratio > self.MAX_FACE_H: reasons.append("Too close")

        if not self.check_liveness(face): reasons.append("Blink eyes")
        is_center, msg = self.is_centered(box, w, h)
        if not (is_center): reasons.append(msg)

        if not reasons:
            self.stability_counter += 1
            progress = min(self.stability_counter / self.STABILITY_THRESHOLD, 1.0)
            
            if self.stability_counter >= self.STABILITY_THRESHOLD:
                status = "STABLE"
                if time.time() - self.last_capture_time > self.COOLDOWN:
                    
                    # Safe dictionary is passed out!
                    captured_face = self.crop_face_native(frame, box)
                    
                    self.last_capture_time = time.time()
                    self.shots_taken += 1
                    if self.shots_taken >= self.MAX_SHOTS:
                        self.is_locked = True
            else:
                status = "STABILIZING"
        else:
            self.stability_counter = 0
            status = "INVALID"
            progress = 0

        return {
            "status": status,
            "reasons": reasons,
            "progress": progress,
            "count": self.shots_taken,
            "max_shots": self.MAX_SHOTS,
            "captured_face": captured_face 
        }