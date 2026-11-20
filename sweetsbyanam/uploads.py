"""Inspiration photos that customers attach to an order.

Safety rules, because these are files from strangers:
  * the file's real type is decided from its first bytes, never from its name or the browser's claim
  * only JPEG, PNG and WebP are accepted (no SVG or HTML, which can carry scripts)
  * at most 5 photos of at most 5 MB each
  * files are saved under random names in a private folder that is NOT part of the public website;
    the only way to see them is through the password-protected dashboard
"""
from __future__ import annotations

import os
import secrets

MAX_IMAGES = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_IMAGES * MAX_IMAGE_BYTES + 256 * 1024  # photos plus the order text
TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def sniff(data: bytes) -> str | None:
    """Return 'jpg', 'png' or 'webp' from the file's leading bytes, or None if it's anything else."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def clean_images(files) -> tuple[list[dict], dict]:
    """Check uploaded files. Returns (accepted images with their bytes, errors keyed 'images')."""
    files = [f for f in files if f and f.filename]
    if len(files) > MAX_IMAGES:
        return [], {"images": f"Please attach at most {MAX_IMAGES} photos."}
    accepted = []
    for f in files:
        data = f.stream.read(MAX_IMAGE_BYTES + 1)
        name = os.path.basename(f.filename.replace("\\", "/"))[:100] or "photo"
        if len(data) > MAX_IMAGE_BYTES:
            return [], {"images": f"'{name}' is larger than {MAX_IMAGE_BYTES // 1024 // 1024} MB. Please choose a smaller photo."}
        kind = sniff(data)
        if kind is None:
            return [], {"images": f"'{name}' isn't a JPG, PNG or WebP photo."}
        accepted.append({"data": data, "ext": kind, "content_type": TYPES[kind], "original_name": name, "size": len(data)})
    return accepted, {}


def store(folder: str, images: list[dict]) -> list[dict]:
    """Write accepted images to disk under random names. Returns rows ready for the database."""
    os.makedirs(folder, exist_ok=True)
    saved = []
    try:
        for im in images:
            filename = f"{secrets.token_hex(16)}.{im['ext']}"
            with open(os.path.join(folder, filename), "wb") as out:
                out.write(im["data"])
            saved.append({"filename": filename, "original_name": im["original_name"],
                          "content_type": im["content_type"], "size": im["size"]})
    except BaseException:
        remove(folder, saved)
        raise
    return saved


def remove(folder: str, saved: list[dict]) -> None:
    for im in saved:
        try:
            os.unlink(os.path.join(folder, im["filename"]))
        except OSError:
            pass
