"""Register a recorded fallback captured at the Nov 30 dress rehearsal.

Usage: python3 tools/register_recording.py <beat: 1|2|3|3v> <path-to-file>
Copies the file into recordings/ under the manifest's name and records sha256, size, duration (ffprobe, if
present) and captured_at. The warm-up refuses a file whose sha256 no longer matches.
"""
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

APP = pathlib.Path(__file__).resolve().parents[1]
MAN = APP / "recordings" / "manifest.json"


def main(beat: str, src: str):
    man = json.loads(MAN.read_text())
    entry = man["beats"][beat]
    dst = APP / "recordings" / entry["file"]
    shutil.copyfile(src, dst)
    entry["sha256"] = hashlib.sha256(dst.read_bytes()).hexdigest()
    entry["captured_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dst)],
                             capture_output=True, text=True, check=True)
        entry["duration_s"] = round(float(out.stdout.strip()), 1)
    except Exception:
        entry["duration_s"] = None
    MAN.write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps({beat: entry}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
