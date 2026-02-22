import sys
import subprocess
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
    ):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.process: Optional[subprocess.Popen] = None
        self.last_file: Optional[Path] = None
        self.is_playing = False

    def start(self, output_file: str):
        # Bloque si lecture en cours
        if self.is_playing:
            return

        if self.process is not None:
            return

        output_path = Path(output_file)

        command = [
            "arecord",
            "-D", self.device,
            "-f", "S16_LE",
            "-r", str(self.sample_rate),
            "-c", str(self.channels),
            "-t", "wav",
            str(output_path),
        ]

        self.process = subprocess.Popen(command)
        self.last_file = output_path
        print("Recording started")

    def stop(self):
        if self.process is None:
            return

        self.process.terminate()
        self.process.wait()
        self.process = None
        print("Recording stopped")

    def play_last(self):
        # Ignore si déjà en lecture
        if self.is_playing:
            return

        # Ignore si enregistrement en cours
        if self.process is not None:
            return

        if self.last_file is None or not self.last_file.exists():
            print("No recording available")
            return

        self.is_playing = True
        try:
            subprocess.run(["aplay", str(self.last_file)], check=True)
        except subprocess.CalledProcessError:
            print("Playback error")
        finally:
            self.is_playing = False


if __name__ == "__main__":
    recorder = AudioRecorder()

    record_button = Button(5, pull_up=True, bounce_time=0.1)
    play_button = Button(6, pull_up=True, bounce_time=0.1)

    record_button.when_pressed = lambda: recorder.start("test.wav")
    record_button.when_released = recorder.stop
    play_button.when_pressed = recorder.play_last

    print("Ready. GPIO5=Record, GPIO6=Play")
    pause()