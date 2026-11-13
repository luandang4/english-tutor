"""Download Kokoro-82M ONNX model files (~340 MB) into data/models/."""

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings  # noqa: E402

BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"


def main() -> None:
    s = get_settings()
    for path in (s.tts_model_path, s.tts_voices_path):
        if path.exists():
            print(f"✓ {path.name} already present")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        print(f"↓ {path.name} …", flush=True)
        urllib.request.urlretrieve(f"{BASE}/{path.name}", tmp)
        tmp.rename(path)
        print(f"✓ {path.name} ({path.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
