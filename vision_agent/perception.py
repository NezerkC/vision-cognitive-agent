"""Perception module for multimodal feature extraction using CLIP."""

import logging
from typing import List, Union
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

class VisionPerceiver:
    """Extracts joint multimodal embeddings (text and image) using CLIP."""

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self._model = None
        self._processor = None
        self._device = "cpu"

    def _lazy_init(self):
        """Lazy load heavy PyTorch and HuggingFace transformers models."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading CLIP model '{self.model_name}' on device '{self._device}'...")
            self._model = CLIPModel.from_pretrained(self.model_name).to(self._device)
            self._processor = CLIPProcessor.from_pretrained(self.model_name)
        except Exception as e:
            logger.warning(f"Could not load HuggingFace CLIP ({e}). Operating in mock perception mode.")
            self._model = None

    def embed_image(self, image_input: Union[str, Image.Image]) -> List[float]:
        """Generate a normalized feature embedding vector for an image."""
        self._lazy_init()
        if self._model is None:
            # Deterministic mock embedding for offline/testing environments
            return list(np.ones(512, dtype=float) / np.sqrt(512))

        import torch
        if isinstance(image_input, str):
            image = Image.open(image_input).convert("RGB")
        else:
            image = image_input

        inputs = self._processor(images=image, return_tensors="pt").to(self._device)
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
            features = features / features.norm(p=2, dim=-1, keepdim=True)
            return features.cpu().numpy()[0].tolist()

    def embed_text(self, text: str) -> List[float]:
        """Generate a normalized feature embedding vector for a text query."""
        self._lazy_init()
        if self._model is None:
            return list(np.ones(512, dtype=float) / np.sqrt(512))

        import torch
        inputs = self._processor(text=[text], return_tensors="pt", padding=True).to(self._device)
        with torch.no_grad():
            features = self._model.get_text_features(**inputs)
            features = features / features.norm(p=2, dim=-1, keepdim=True)
            return features.cpu().numpy()[0].tolist()
