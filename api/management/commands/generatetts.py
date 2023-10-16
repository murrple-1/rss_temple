import os
import subprocess
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.captcha import ALPHABET as CAPTCHA_ALPHABET


class Command(BaseCommand):
    help = "Generate voice clips for the captcha"

    def add_arguments(self, parser: CommandParser) -> None:  # pragma: no cover
        parser.add_argument("voices_dir")
        parser.add_argument("-a", "--espeak-amplitude", type=int, default=150)
        parser.add_argument("-s", "--espeak-speed", type=int, default=150)
        parser.add_argument("-p", "--espeak-pitch", type=int, default=50)
        parser.add_argument("-w", "--wav-filename", default="default.wav")

    def handle(self, *args: Any, **options: Any) -> None:
        espeak_amplitude_str = str(options["espeak_amplitude"])
        espeak_speed_str = str(options["espeak_speed"])
        espeak_pitch_str = str(options["espeak_pitch"])

        # via https://captcha.lepture.com/audio/#voice-library
        for c in CAPTCHA_ALPHABET:
            voice_dir = os.path.join(options["voices_dir"], c)
            os.makedirs(voice_dir, exist_ok=True, mode=0o777)
            orig_filepath = os.path.join(voice_dir, "orig_default.wav")
            filepath = os.path.join(voice_dir, options["wav_filename"])
            subprocess.run(
                [
                    "espeak",
                    "-a",
                    espeak_amplitude_str,
                    "-s",
                    espeak_speed_str,
                    "-p",
                    espeak_pitch_str,
                    "-v",
                    "en",
                    c,
                    "-w",
                    orig_filepath,
                ]
            )
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        orig_filepath,
                        "-ar",
                        "8000",
                        "-ac",
                        "1",
                        "-acodec",
                        "pcm_u8",
                        filepath,
                    ]
                )
            finally:
                os.unlink(orig_filepath)
