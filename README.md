# Facial Recognition Attendance Tracker

A robust, multi-screen Kivy application designed for Android and Desktop platforms. This app provides offline-first facial registration, live recognition, and automated background network synchronization for tracking daily attendance.

## Key Features

* **Face Registration & Storage:** Capture and store user faces locally. Facial embeddings are securely saved in a local SQLite database (`faces.db`) for offline use.
* **Live Facial Recognition:** Real-time scanning and matching against registered users.
* **Offline-First Attendance Logging:** Successful recognitions are immediately logged with precise timestamps into a local database (`attendance.db`). 
* **User Management:** View all registered users in a clean UI. Features a safe, one-click deletion system that completely removes physical image folders and database embeddings with a confirmation safeguard.
* **Dynamic Network Synchronization:** * Customizable Host IP configuration directly from the UI.
    * **Auto-Sync:** Background synchronization loop that sends new attendance logs to a central server every 60 seconds without freezing the app.
    * **Manual Sync:** Push data instantly at the tap of a button.
    * **Smart Payload:** Only unsynced records are transmitted, saving bandwidth and preventing duplicate database entries.

## Tech Stack

* **Frontend / Mobile Framework:** Kivy & KivyMD
* **Facial Recognition:** OpenCV / Face_recognition (or your specific ML model)
* **Local Database:** SQLite3 (`faces.db`, `attendance.db`)
* **Networking:** Python `requests` (client), Flask (expected backend)

## Project Structure

```text
📁 Project Root
│
├── main.py                   # App entry point & ScreenManager setup
├── network_sync.py           # AttendanceSyncer background thread logic
├── registration_screen.py    # Face capturing and embedding generation
├── view_faces_screen.py      # User management, gallery, and data deletion
├── recognition_screen.py     # Live camera feed and matching logic
├── log_history_screen.py     # Attendance UI, IP configuration, and Sync controls
│
└── 📁 user_data_dir/registered_faces/  # Automatically generated on first run
    ├── faces.db              # Stores user names and facial embeddings
    ├── attendance.db         # Stores timestamps and sync status
    ├── 📁 User_Name_1/       # Physical images of User 1
    └── 📁 User_Name_2/       # Physical images of User 2
```

## Getting Started

### Prerequisites
Make sure you have Python 3 installed, along with the required libraries.
```bash
pip install kivy opencv-python sqlite3 requests
```
*(Note: Add any specific facial recognition or camera libraries your project relies on, such as `face_recognition` or `kivy.core.camera`)*

### Running the App
Execute the main file to launch the application:
```bash
python main.py
```

### Backend Setup (Server-side)
To use the network sync feature, you will need a lightweight Flask server running on your network. The app expects a `POST` request to:
`http://<YOUR_IP_ADDRESS>:5000/sync`

The app sends a JSON payload structured like this:
```json
[
  {"id": 1, "person_name": "John Doe", "timestamp": "2026-04-30 08:00:00"},
  {"id": 2, "person_name": "Jane Smith", "timestamp": "2026-04-30 08:05:00"}
]
```

## User Guide

1.  **Register a New Face:** Go to the Registration screen, enter the person's name, and follow the camera prompts to generate their profile and database embeddings.
2.  **Start Live Recognition:** Open the Live Recognition screen and point the camera at a registered user. The system will recognize them and instantly log their attendance.
3.  **Manage Users:** Go to "View Registered Faces" to see all users. You can safely delete users here—this wipes their photos and database memory simultaneously.
4.  **Sync Attendance:** * Navigate to the "Attendance List" screen.
    * Enter the IP address of your host server
    * Toggle **Auto-Sync** to let the app handle data transfers in the background, or press **Manual Sync Now** to push data immediately.
