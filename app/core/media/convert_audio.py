import subprocess
import tempfile
from pathlib import Path


def to_mp3(audio_bytes: bytes, input_extension: str) -> bytes:
    """Convert audio bytes to mp3 using ffmpeg."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_path = tmpdir_path / f"input.{input_extension}"
        output_path = tmpdir_path / "audio.mp3"
        input_path.write_bytes(audio_bytes)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(input_path),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    str(output_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("ffmpeg failed to convert audio to mp3") from exc

        return output_path.read_bytes()
