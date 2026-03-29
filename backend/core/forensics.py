"""Forensic metadata extraction for images and PDF artifacts."""

from __future__ import annotations

from io import BytesIO

from PIL import ExifTags, Image
from PyPDF2 import PdfReader

from .http_client import build_request_headers, build_live_url


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".tiff")
PDF_EXTENSIONS = (".pdf",)


def _gps_to_decimal(coords):
    try:
        degrees = float(coords[0])
        minutes = float(coords[1]) / 60.0
        seconds = float(coords[2]) / 3600.0
        return degrees + minutes + seconds
    except Exception:
        return None


def _decode_exif(raw_exif):
    if not raw_exif:
        return {}

    decoded = {}
    for tag_id, value in raw_exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        if tag_name == "GPSInfo" and isinstance(value, dict):
            gps = {}
            for gps_tag_id, gps_value in value.items():
                gps_name = ExifTags.GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                gps[gps_name] = gps_value

            latitude = _gps_to_decimal(gps.get("GPSLatitude", ()))
            longitude = _gps_to_decimal(gps.get("GPSLongitude", ()))
            if gps.get("GPSLatitudeRef") == "S" and latitude is not None:
                latitude *= -1
            if gps.get("GPSLongitudeRef") == "W" and longitude is not None:
                longitude *= -1

            if latitude is not None and longitude is not None:
                decoded["gps"] = {"latitude": latitude, "longitude": longitude}
            continue

        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="ignore")
            except Exception:
                continue

        if isinstance(value, (str, int, float)):
            decoded[tag_name.lower()] = value

    return decoded


async def extract_image_metadata(client, image_url: str, timeout: float = 10.0) -> dict | None:
    """Fetch an image and extract basic EXIF metadata."""
    response = await client.get(
        build_live_url(image_url),
        headers=build_request_headers(),
        timeout=timeout,
        follow_redirects=True,
    )
    if response.status_code != 200:
        return None

    image = Image.open(BytesIO(response.content))
    exif = _decode_exif(image.getexif())
    return {
        "resource_type": "image",
        "url": str(response.url),
        "content_type": response.headers.get("content-type", ""),
        "width": image.width,
        "height": image.height,
        "exif": exif,
    }


async def extract_pdf_metadata(client, pdf_url: str, timeout: float = 10.0) -> dict | None:
    """Fetch a PDF and extract basic document metadata."""
    response = await client.get(
        build_live_url(pdf_url),
        headers=build_request_headers(),
        timeout=timeout,
        follow_redirects=True,
    )
    if response.status_code != 200:
        return None

    reader = PdfReader(BytesIO(response.content))
    metadata = {}
    if reader.metadata:
        for key, value in reader.metadata.items():
            metadata[str(key).lstrip("/").lower()] = str(value)

    return {
        "resource_type": "pdf",
        "url": str(response.url),
        "content_type": response.headers.get("content-type", ""),
        "pages": len(reader.pages),
        "metadata": metadata,
    }
