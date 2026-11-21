"""D03 voice seam: local speech-to-text -> Request(channel="voice"), with a typed fallback and a recorded clip.

R5.2 default (option A): live speech-to-text, typed fallback, recorded clip if the room is loud.
Offline only: nothing here calls a network service. Engines are tried in order and skipped if absent:
  1. mlx_whisper (Apple silicon; the stage host)         pip install mlx-whisper; model from the demo bundle
  2. whisper.cpp CLI (WHISPER_CPP_BIN + model)  any host
The browser posts the recorded audio; if no engine answers inside `timeout_s` the operator types the
words (typed fallback, < 5 s oracle) and the Request is still channel="voice". How the words arrived
(stt | typed | clip) is telemetry metadata (`input_mode`), never a Request field.
"""
from __future__ import annotations

import concurrent.futures as cf
import os
import shutil
import subprocess
import tempfile
import time


class SpeechToText:
    def __init__(self, engine: str = "auto", timeout_s: float = 4.0, model: str | None = None):
        self.engine_pref, self.timeout_s, self.model = engine, timeout_s, model
        self.engine = self._detect()

    def _detect(self) -> str | None:
        prefs = ["mlx_whisper", "whisper_cpp"] if self.engine_pref == "auto" else [self.engine_pref]
        for name in prefs:
            if name == "mlx_whisper":
                try:
                    import mlx_whisper  # noqa: F401
                    return "mlx_whisper"
                except Exception:
                    continue
            if name == "whisper_cpp":
                binary = os.environ.get("WHISPER_CPP_BIN") or shutil.which("whisper-cli") or shutil.which("main")
                if binary and os.environ.get("WHISPER_CPP_MODEL"):
                    self._wcpp = binary
                    return "whisper_cpp"
        return None

    def status(self) -> dict:
        return {"engine": self.engine, "timeout_s": self.timeout_s, "available": self.engine is not None}

    def _run(self, path: str) -> str:
        if self.engine == "mlx_whisper":
            import mlx_whisper
            out = mlx_whisper.transcribe(path, path_or_hf_repo=self.model or os.environ.get("MLX_WHISPER_MODEL", "mlx-community/whisper-small-mlx"),
                                         language="en", temperature=0.0)
            return out["text"].strip()
        if self.engine == "whisper_cpp":
            wav = path + ".wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ar", "16000", "-ac", "1", wav], check=True, timeout=self.timeout_s)
            res = subprocess.run([self._wcpp, "-m", os.environ["WHISPER_CPP_MODEL"], "-f", wav, "-nt", "-l", "en"],
                                 capture_output=True, text=True, check=True, timeout=self.timeout_s)
            return " ".join(res.stdout.split())
        raise RuntimeError("no local speech-to-text engine")

    def transcribe(self, audio: bytes, suffix: str = ".webm") -> dict:
        """Return {ok, text, input_mode, engine, ms, error?}. Never raises; a failure means 'type it'."""
        t0 = time.time()
        if not self.engine:
            return {"ok": False, "text": "", "input_mode": "stt", "engine": None, "ms": 0, "error": "no engine: use typed fallback"}
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio)
            path = f.name
        pool = cf.ThreadPoolExecutor(max_workers=1)
        try:
            text = pool.submit(self._run, path).result(timeout=self.timeout_s)
            return {"ok": bool(text), "text": text, "input_mode": "stt", "engine": self.engine, "ms": int((time.time() - t0) * 1000)}
        except Exception as exc:
            return {"ok": False, "text": "", "input_mode": "stt", "engine": self.engine, "ms": int((time.time() - t0) * 1000),
                    "error": f"{type(exc).__name__}: {exc}"}
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            for p in (path, path + ".wav"):
                try:
                    os.unlink(p)
                except OSError:
                    pass


def voice_request(text: str, *, member_hash: str, received_at: str, locale: str = "en-US") -> dict:
    """The Request the voice seam hands to K01, whatever the input mode."""
    return {"text": text.strip(), "actor": {"member_hash": member_hash, "role": "requester"}, "channel": "voice",
            "locale": locale, "received_at": received_at}
