"""Build the local pronunciation model: facebook/wav2vec2-lv-60-espeak-cv-ft (Apache-2.0) -> ONNX -> int8.

Needs PyTorch, which the app itself does not use, so run it in a throwaway environment:

    uv venv --python 3.12 /tmp/w2v && uv pip install --python /tmp/w2v "torch==2.2.2" "numpy<2" \
        "transformers==4.46.3" "onnx==1.16.2" "onnxruntime==1.20.1" "huggingface_hub<0.27"
    /tmp/w2v/bin/python -I backend/scripts/export_phoneme_model.py data/models

(torch 2.2 is the last release with Intel-Mac wheels; any newer torch works on Linux / Apple Silicon.)
Output: data/models/wav2vec2-phoneme-int8.onnx (~356 MB) + wav2vec2-phoneme-vocab.json.
"""

import json
import sys
import tempfile
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download
from onnxruntime.quantization import QuantType, quantize_dynamic
from transformers import Wav2Vec2ForCTC

REPO = "facebook/wav2vec2-lv-60-espeak-cv-ft"


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    model = Wav2Vec2ForCTC.from_pretrained(REPO).eval()
    with tempfile.TemporaryDirectory() as tmp:
        fp32 = Path(tmp) / "w2v.onnx"
        torch.onnx.export(
            model,
            (torch.zeros(1, 16000 * 3),),
            fp32,
            input_names=["input_values"],
            output_names=["logits"],
            dynamic_axes={"input_values": {0: "b", 1: "t"}, "logits": {0: "b", 1: "f"}},
            opset_version=14,
        )
        # MatMul/Gemm only: quantized Conv (ConvInteger) has no CPU kernel in onnxruntime.
        quantize_dynamic(
            fp32,
            out / "wav2vec2-phoneme-int8.onnx",
            weight_type=QuantType.QInt8,
            op_types_to_quantize=["MatMul", "Gemm"],
        )
    vocab = json.loads(Path(hf_hub_download(REPO, "vocab.json")).read_text())
    (out / "wav2vec2-phoneme-vocab.json").write_text(json.dumps(vocab, ensure_ascii=False))
    print(f"done: {out / 'wav2vec2-phoneme-int8.onnx'}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/models"))
