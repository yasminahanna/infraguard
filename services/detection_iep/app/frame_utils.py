import base64

import cv2
import numpy as np
from PIL import Image


def decode_base64_frame(frame_base64: str) -> np.ndarray | None:
    try:
        if "," in frame_base64:
            frame_base64 = frame_base64.split(",", 1)[1]

        image_bytes = base64.b64decode(frame_base64, validate=True)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        return image
    except Exception:
        return None


def cv2_to_pil(image: np.ndarray) -> Image.Image:
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_image)