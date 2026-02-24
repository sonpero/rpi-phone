import sys
import subprocess
import re
from time import sleep
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
    ):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.process: Optional[subprocess.Popen] = None
        self.last_file: Optional[Path] = None


    def create_time_stamp_suffix(self):
        suffix = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        return suffix

    def start(self, output_file_path: str):

        if self.process is not None:
            return

        subprocess.run(["aplay", "tone_440.wav"])
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

        self.process = subprocess.Popen(command)
        self.last_file = Path(output_path)
        print("Recording started")

    def stop(self):
        if self.process is None:
            return

        self.process.terminate()
        self.process.wait()
        self.process = None
        print("Recording stopped")

    def play_last(self):
        # Ignore si enregistrement en cours
        if self.process is not None:
            return

        if self.last_file is None or not self.last_file.exists():
            print("No recording available")
            return
        
        try:
            playback_process = subprocess.Popen(["aplay", str(self.last_file)])
        except Exception as e:
            print("Playback error", e)


if __name__ == "__main__":

    recorder = AudioRecorder()

    record_button = Button(5, pull_up=True, bounce_time=0.1)
    play_button = Button(6, pull_up=True, bounce_time=0.1)

    record_button.when_pressed = lambda: recorder.start("/home/alex/phone/messages")
    record_button.when_released = recorder.stop
    play_button.when_pressed = recorder.play_last

    print("Ready. GPIO5=Record, GPIO6=Play")
    pause()