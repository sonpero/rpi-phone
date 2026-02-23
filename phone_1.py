import sys
import subprocess
import re
from time import sleep
from pathlib import Path
from typing import Optional
from gpiozero import Button
from signal import pause


class RepoScanner:
    def __init__(self, directory: str):
        self.directory = Path(directory)

    def get_last_file(self) -> Optional[Path]:
        if not self.directory.exists():
            return None

        pattern = re.compile(r"message_(\d+)\.wav$")
        max_index = -1
        last_file = None

        for file in self.directory.iterdir():
            if not file.is_file():
                continue

            match = pattern.match(file.name)
            if match:
                index = int(match.group(1))
                if index > max_index:
                    max_index = index
                    last_file = file

        return last_file


class AudioRecorder:
    def __init__(
        self,
        repo_scanner,
        device: str = "hw:0,0",
        sample_rate: int = 16000,
        channels: int = 2,
    ):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.repo_scanner = repo_scanner
        self.process: Optional[subprocess.Popen] = None
        self.last_file: Optional[Path] = None
        self.is_playing = False
        self.last = None
        self.index = None
        self.find_last_message_index()

    def find_last_message_index(self):
        self.last = self.repo_scanner.get_last_file()
        print("repo path", self.repo_scanner.directory)
        print("last", self.last)
        if self.last is None :
            self.index = 0
            return
        self.index = int(self.last.split(".")[0].split("_")[-1])
        return

    def start(self, output_file: str):
        # Bloque si lecture en cours
        if self.is_playing:
            return

        if self.process is not None:
            return

        subprocess.run(["aplay", "tone_440.wav"])
        self.index += 1
        output_path = f'{self.repo_scanner.directory}/{output_file.split(".")[0]}_{str(self.index)}.wav'
        print("output path", output_path)
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
    repo_scanner = RepoScanner("/home/alex/phone/messages")
    recorder = AudioRecorder(repo_scanner)

    record_button = Button(5, pull_up=True, bounce_time=0.1)
    play_button = Button(6, pull_up=True, bounce_time=0.1)

    record_button.when_pressed = lambda: recorder.start("message.wav")
    record_button.when_released = recorder.stop
    play_button.when_pressed = recorder.play_last

    print("Ready. GPIO5=Record, GPIO6=Play")
    pause()