import subprocess
import threading

from datetime import datetime
from pathlib import Path
from typing import Optional
from gpiozero import Button
from signal import pause


class AudioRecorder:
    def __init__(
        self,
        device: str = "hw:0,0",
        sample_rate: int = 16000,
        channels: int = 2,
        max_duration: int = (60),
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

    def create_time_stamp_suffix(self):
        suffix = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        return suffix

    def start(self, output_file_path: str):
        if self.process is not None:
            return

        # Reset the max duration flag
        self.max_duration_reached = False

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
        subprocess.run(["aplay", "tone_440.wav"])

        # Start timer for maximum duration
        self.timer = threading.Timer(self.max_duration, self._on_max_duration_reached)
        self.timer.start()

    def stop(self):
        # Cancel the timer if it's running
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

        if self.recording_process is None:
            process = self.playing_process
            self.playing_process = None
        else:
            process = self.recording_process
            self.recording_process = None

        if process is not None:
            process.terminate()
            process.wait()
            print("Stopped")

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
            subprocess.run(["aplay", "tone_440.wav"])
        

if __name__ == "__main__":

    recorder = AudioRecorder()

    record_button = Button(5, pull_up=True, bounce_time=0.1)
    play_button = Button(6, pull_up=True, bounce_time=0.1)

    record_button.when_pressed = lambda: recorder.start("/home/alex/phone/messages")
    record_button.when_released = recorder.on_record_released
    play_button.when_pressed = lambda: recorder.cancel_and_play_last(record_button)

    print("Ready. GPIO5=Record, GPIO6=Play/Cancel")
    pause()