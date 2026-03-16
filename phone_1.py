import subprocess
import threading
import os
import io
import zipfile
import json

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote

from datetime import datetime
from pathlib import Path
from typing import Optional
from gpiozero import Button
from signal import pause

MESSAGES_DIR = Path("/home/alex/phone/messages")


class AudioRecorder:
    def __init__(
        self,
        device: str = "hw:0,0",
        sample_rate: int = 16000,
        channels: int = 2,
        max_duration: int = 180,
    ):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_duration = max_duration
        self.process: Optional[subprocess.Popen] = None
        self.last_file: Optional[Path] = None
        self.cancelled = False
        self.max_duration_reached = False
        self.timer: Optional[threading.Timer] = None
        self.playing_process = None
        self.playing_welcome_process = None
        self.recording_process = None
        self._stop_requested = False
        self._start_lock = threading.Lock()

    def create_time_stamp_suffix(self):
        suffix = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        return suffix

    def start(self, output_file_path: str):
        """Run the full start sequence in a background thread."""
        threading.Thread(
            target=self._start_sequence,
            args=(output_file_path,),
            daemon=True,
        ).start()

    def _start_sequence(self, output_file_path: str):
        with self._start_lock:
            self._stop_requested = False

            # --- Play dial tone ---
            proc = subprocess.Popen(
                ["aplay", "/home/alex/phone/rpi-phone/tone_440.wav"]
            )
            proc.wait()
            if self._stop_requested:
                print("Stop requested after dial tone, aborting start")
                return

            # --- Play welcome message ---
            self.playing_welcome_process = subprocess.Popen(
                ["aplay", "/home/alex/phone/rpi-phone/welcome_message.wav"]
            )
            self.playing_welcome_process.wait()
            # Check AFTER wait returns — was it killed or did it finish naturally?
            if self._stop_requested:
                self.playing_welcome_process = None
                print("Stop requested during welcome message, aborting start")
                return
            self.playing_welcome_process = None

            # --- Play beep tone ---
            proc = subprocess.Popen(
                ["aplay", "/home/alex/phone/rpi-phone/tone_440.wav"]
            )
            proc.wait()
            if self._stop_requested:
                print("Stop requested after beep tone, aborting start")
                return

            # --- Start recording ---
            suffix = self.create_time_stamp_suffix()
            output_path = f'{output_file_path}/message_{suffix}.wav'
            command = [
                "arecord",
                "-D", self.device,
                "-f", "S16_LE",
                "-r", str(self.sample_rate),
                "-c", str(self.channels),
                "-t", "wav",
                str(output_path),
            ]

            self.recording_process = subprocess.Popen(command)
            self.last_file = Path(output_path)
            print("Recording started")

            # Start timer for maximum duration
            self.timer = threading.Timer(
                self.max_duration, self._on_max_duration_reached
            )
            self.timer.start()

    def stop(self):
        # Signal the start sequence to abort at the next checkpoint
        self._stop_requested = True

        # Cancel the timer if it's running
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

        # Kill the welcome message if still playing
        if self.playing_welcome_process is not None:
            try:
                self.playing_welcome_process.terminate()
                self.playing_welcome_process.wait()
            except Exception:
                pass
            self.playing_welcome_process = None
            print("Stopped welcome message")

        # Kill the recording if active
        if self.recording_process is not None:
            self.recording_process.terminate()
            self.recording_process.wait()
            self.recording_process = None
            print("Recording stopped")

        # Kill playback if active
        if self.playing_process is not None:
            self.playing_process.terminate()
            self.playing_process.wait()
            self.playing_process = None
            print("Playback stopped")

    def cancel_recording(self):
        """Arrête l'enregistrement en cours sans sauvegarder le fichier."""
        # Cancel the timer if it's running
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        
        if self.recording_process is None :
            return

        current_file = self.last_file

        self.recording_process.terminate()
        self.recording_process.wait()
        self.recording_process = None

        # Supprime le fichier enregistré
        if current_file is not None and current_file.exists():
            current_file.unlink()
            print(f"Recording cancelled, file deleted: {current_file}")

        # Restaure last_file au fichier précédent si disponible
        self._restore_last_file(current_file)

    def _restore_last_file(self, cancelled_file: Optional[Path]):
        """Retrouve le dernier fichier valide après annulation."""
        folder = cancelled_file.parent if cancelled_file else None
        if folder is None or not folder.exists():
            self.last_file = None
            return

        wav_files = sorted(folder.glob("message_*.wav"))
        if wav_files:
            self.last_file = wav_files[-1]
            print(f"Last available file restored: {self.last_file}")
        else:
            self.last_file = None
            print("No previous recording available")

    def play_last(self):
        if self.recording_process is not None:
            return

        if self.last_file is None or not self.last_file.exists():
            print("No recording available")
            return

        try:
            self.playing_process = subprocess.Popen(["aplay", str(self.last_file)])
        except Exception as e:
            print("Playback error", e)

    def cancel_and_play_last(self, record_button: Button):
        """Annule l'enregistrement en cours et lit le dernier message."""
        if record_button.is_pressed:
            print("Cancel mode: stopping recording without saving and playing last message")
            self.cancelled = True
            if self.recording_process is not None :
                self.cancel_recording()
                self.play_last()
            else:
                self.stop()
                self.play_last()

            if self.playing_welcome_process is not None:
                self.playing_welcome_process.terminate()
                self.playing_welcome_process.wait()
                self.stop()
                self.play_last()

    def on_record_released(self):
        """Gère le relâchement du bouton d'enregistrement."""
        self.stop()
        if self.cancelled:
            print("Button 5 released after cancel, system ready")
            self.cancelled = False
            return

    def _on_max_duration_reached(self):
        """Called when maximum recording duration is reached."""
        print(f"Maximum recording duration ({self.max_duration}s) reached")
        self.max_duration_reached = True
        if self.recording_process is not None:
            self.stop()
            print("Recording stopped automatically")
            subprocess.run(["aplay", "/home/alex/phone/rpi-phone/tone_440.wav"])
        

class MessageHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/" or self.path == "/index.html":
            self.serve_index()

        elif self.path.startswith("/files/"):
            self.serve_file(self.path[len("/files/"):])

        else:
            self.send_error(404)

    def do_POST(self):

        if self.path == "/download_zip":

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            data = json.loads(body.decode())
            files = data.get("files", [])

            buffer = io.BytesIO()

            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
                for name in files:
                    path = MESSAGES_DIR / name
                    if path.exists():
                        z.write(path, arcname=name)

            zip_data = buffer.getvalue()

            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=messages.zip")
            self.send_header("Content-Length", str(len(zip_data)))
            self.end_headers()

            self.wfile.write(zip_data)

        elif self.path == "/delete":

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            data = json.loads(body.decode())
            files = data.get("files", [])

            deleted = []

            for name in files:
                path = MESSAGES_DIR / name
                if path.exists():
                    path.unlink()
                    deleted.append(name)

            resp = json.dumps({"deleted": deleted}).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()

            self.wfile.write(resp)

        else:
            self.send_error(404)

    def serve_file(self, filename):

        filename = unquote(filename)
        path = MESSAGES_DIR / filename

        if not path.exists():
            self.send_error(404)
            return

        with open(path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

        self.wfile.write(data)

    def serve_index(self):

        files = sorted(
            MESSAGES_DIR.glob("message_*.wav"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        rows = []

        for f in files:
            name = f.name

            rows.append(
                f"""
<div class="msg">
<input type="checkbox" class="chk" value="{name}">
<div class="name">{name}</div>
<audio controls src="/files/{name}"></audio>
<a href="/files/{name}" download>Download</a>
</div>
"""
            )

        html = f"""
<!DOCTYPE html>
<html>

<head>

<meta name="viewport" content="width=device-width, initial-scale=1">

<style>

body{{font-family:sans-serif;margin:20px;background:#f5f5f5}}

.msg{{background:white;padding:12px;margin-bottom:12px;border-radius:8px}}

.name{{font-size:14px;margin-bottom:6px}}

audio{{width:100%}}

button{{margin-bottom:12px;padding:8px 12px;margin-right:6px}}

</style>

<script>

function selectAll(){{
document.querySelectorAll(".chk").forEach(c=>c.checked=true);
}}

function downloadSelected(){{

const files=[...document.querySelectorAll(".chk:checked")].map(c=>c.value);

if(files.length===0){{
alert("No messages selected");
return;
}}

fetch("/download_zip",{{
method:"POST",
headers:{{"Content-Type":"application/json"}},
body:JSON.stringify({{files:files}})
}})
.then(r=>r.blob())
.then(blob=>{{
const url=window.URL.createObjectURL(blob);
const a=document.createElement("a");
a.href=url;
a.download="messages.zip";
document.body.appendChild(a);
a.click();
a.remove();
}});

}}

function deleteSelected(){{

const files=[...document.querySelectorAll(".chk:checked")].map(c=>c.value);

if(files.length===0){{
alert("No messages selected");
return;
}}

if(!confirm("Delete selected messages?")){{
return;
}}

fetch("/delete",{{
method:"POST",
headers:{{"Content-Type":"application/json"}},
body:JSON.stringify({{files:files}})
}})
.then(r=>r.json())
.then(()=>{{
location.reload();
}});

}}

</script>

</head>

<body>

<h2>Messages</h2>

<button onclick="selectAll()">Select all</button>
<button onclick="downloadSelected()">Download selected</button>
<button onclick="deleteSelected()">Delete selected</button>

{''.join(rows)}

</body>
</html>
"""

        data = html.encode()

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

        self.wfile.write(data)
        

def start_http_server():
    server = ThreadingHTTPServer(("0.0.0.0", 8000), MessageHandler)

    threading.Thread(
        target=server.serve_forever,
        daemon=True
    ).start()

    print("HTTP server running on port 8000")


if __name__ == "__main__":
    start_http_server()
    
    recorder = AudioRecorder()

    record_button = Button(5, pull_up=True, bounce_time=0.1)
    play_button = Button(6, pull_up=True, bounce_time=0.1)

    record_button.when_pressed = lambda: recorder.start("/home/alex/phone/messages")
    record_button.when_released = recorder.on_record_released
    play_button.when_pressed = lambda: recorder.cancel_and_play_last(record_button)

    print("Ready. GPIO5=Record, GPIO6=Play/Cancel")
    pause()