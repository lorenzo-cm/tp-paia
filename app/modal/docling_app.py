import os
from io import BytesIO

import modal
from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter

MODAL_APP_NAME = os.getenv("MODAL_APP_NAME", "template-document-processor")
MODAL_FUNCTION_NAME = os.getenv("MODAL_FUNCTION_NAME", "extract_markdown")
CACHE_DIR = "/template-docling-cache"

app = modal.App(name=MODAL_APP_NAME)
cache_volume = modal.Volume.from_name("template-docling-cache", create_if_missing=True)
_converter: DocumentConverter | None = None


def download_ocr_models() -> None:
    """Donwload the OCR models for caching purposes"""
    from rapidocr import EngineType, RapidOCR

    RapidOCR(
        params={
            "Det.engine_type": EngineType.TORCH,
            "Cls.engine_type": EngineType.TORCH,
            "Rec.engine_type": EngineType.TORCH,
            "Det.use_cuda": True,
            "Cls.use_cuda": True,
            "Rec.use_cuda": True,
            "EngineConfig.torch.use_cuda": True,
            "EngineConfig.torch.cuda_ep_cfg.device_id": 0,
        }
    )


def get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter


docling_image = (
    modal.Image.debian_slim(python_version="3.14")
    .apt_install(
        "libgl1-mesa-glx",
        "libglib2.0-0",
    )
    .pip_install("docling>=2.91.0")
    .run_function(download_ocr_models, gpu="T4")
)


@app.function(
    name=MODAL_FUNCTION_NAME,
    image=docling_image,
    # cache directory for OCR models
    env={
        "HF_HOME": f"{CACHE_DIR}/huggingface",
        "HUGGINGFACE_HUB_CACHE": f"{CACHE_DIR}/huggingface/hub",
        "XDG_CACHE_HOME": CACHE_DIR,
    },
    gpu="T4",
    timeout=30 * 60,
    volumes={CACHE_DIR: cache_volume},
)
def extract_markdown(file_bytes: bytes) -> str:
    converter = get_converter()
    stream = DocumentStream(name="document.pdf", stream=BytesIO(file_bytes))
    result = converter.convert(stream)
    return result.document.export_to_markdown(traverse_pictures=True)
