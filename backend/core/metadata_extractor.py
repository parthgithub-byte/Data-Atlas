"""Metadata & EXIF Forensic Harvester — Deep-file forensics for PDFs, images, and avatars.

Extracts hidden metadata that basic scrapers miss:
  - PDF: Author, Creator, Producer, timestamps
  - Image EXIF: GPS coordinates, camera model, software, creation time
  - Avatar: Perceptual hash for cross-platform visual fingerprinting
"""

import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_pdf_metadata(content_bytes: bytes) -> dict:
    """Extract metadata from a PDF file's binary content.

    Returns dict with author, creator, producer, creation_date, mod_date.
    """
    metadata = {"type": "pdf"}
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(content_bytes))
        info = reader.metadata
        if info:
            metadata["author"] = str(info.get("/Author", "")) or None
            metadata["creator"] = str(info.get("/Creator", "")) or None
            metadata["producer"] = str(info.get("/Producer", "")) or None
            metadata["title"] = str(info.get("/Title", "")) or None
            metadata["subject"] = str(info.get("/Subject", "")) or None

            # Parse dates
            for key, field in [("/CreationDate", "creation_date"), ("/ModDate", "mod_date")]:
                raw = str(info.get(key, ""))
                if raw and raw.startswith("D:"):
                    try:
                        date_str = raw[2:16]  # D:YYYYMMDDHHmmSS
                        metadata[field] = datetime.strptime(date_str, "%Y%m%d%H%M%S").isoformat()
                    except Exception:
                        metadata[field] = raw

            metadata["page_count"] = len(reader.pages)
    except ImportError:
        logger.warning("PyPDF2 not installed — skipping PDF metadata extraction")
    except Exception as e:
        logger.warning(f"PDF metadata extraction failed: {e}")

    # Remove None/empty values
    return {k: v for k, v in metadata.items() if v}


def extract_image_exif(content_bytes: bytes) -> dict:
    """Extract EXIF metadata from an image file.

    Returns dict with GPS coordinates, camera model, software, datetime.
    """
    metadata = {"type": "image"}
    try:
        import exifread
        tags = exifread.process_file(io.BytesIO(content_bytes), details=False)

        # Camera info
        if "Image Make" in tags:
            metadata["camera_make"] = str(tags["Image Make"])
        if "Image Model" in tags:
            metadata["camera_model"] = str(tags["Image Model"])
        if "Image Software" in tags:
            metadata["software"] = str(tags["Image Software"])

        # Datetime
        if "EXIF DateTimeOriginal" in tags:
            metadata["datetime_original"] = str(tags["EXIF DateTimeOriginal"])
        elif "Image DateTime" in tags:
            metadata["datetime_original"] = str(tags["Image DateTime"])

        # GPS coordinates
        gps_lat = tags.get("GPS GPSLatitude")
        gps_lat_ref = tags.get("GPS GPSLatitudeRef")
        gps_lon = tags.get("GPS GPSLongitude")
        gps_lon_ref = tags.get("GPS GPSLongitudeRef")

        if gps_lat and gps_lon:
            try:
                lat = _convert_gps_to_decimal(gps_lat.values, str(gps_lat_ref))
                lon = _convert_gps_to_decimal(gps_lon.values, str(gps_lon_ref))
                metadata["gps_latitude"] = round(lat, 6)
                metadata["gps_longitude"] = round(lon, 6)
                metadata["gps_location"] = f"{lat:.4f}, {lon:.4f}"
            except Exception:
                pass

        # Image dimensions
        if "EXIF ExifImageWidth" in tags:
            metadata["width"] = str(tags["EXIF ExifImageWidth"])
        if "EXIF ExifImageLength" in tags:
            metadata["height"] = str(tags["EXIF ExifImageLength"])

    except ImportError:
        logger.warning("exifread not installed — skipping EXIF extraction")
    except Exception as e:
        logger.warning(f"EXIF extraction failed: {e}")

    return {k: v for k, v in metadata.items() if v}


def _convert_gps_to_decimal(dms_values, ref: str) -> float:
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    d = float(dms_values[0])
    m = float(dms_values[1])
    s = float(dms_values[2])
    decimal = d + (m / 60.0) + (s / 3600.0)
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def compute_avatar_hash(content_bytes: bytes) -> str:
    """Compute a perceptual hash (phash) for an avatar image.

    Returns hex string of the hash, or empty string on failure.
    """
    try:
        import imagehash
        from PIL import Image
        img = Image.open(io.BytesIO(content_bytes))
        phash = imagehash.phash(img)
        return str(phash)
    except ImportError:
        logger.warning("imagehash/Pillow not installed — skipping avatar hashing")
    except Exception as e:
        logger.warning(f"Avatar hash computation failed: {e}")
    return ""


def extract_file_metadata(url: str, content_bytes: bytes, content_type: str) -> dict:
    """Route binary content to the appropriate metadata extractor.

    Args:
        url: Source URL of the file.
        content_bytes: Raw binary content.
        content_type: HTTP Content-Type header value.

    Returns:
        dict with extracted metadata, or empty dict if unsupported.
    """
    content_type = (content_type or "").lower()
    result = {"source_url": url}

    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        result.update(extract_pdf_metadata(content_bytes))
    elif any(t in content_type for t in ["image/jpeg", "image/png", "image/tiff", "image/webp"]):
        result.update(extract_image_exif(content_bytes))
        # Also compute avatar hash for any image
        phash = compute_avatar_hash(content_bytes)
        if phash:
            result["avatar_hash"] = phash
    elif url.lower().endswith((".jpg", ".jpeg", ".png", ".tiff", ".webp")):
        result.update(extract_image_exif(content_bytes))
        phash = compute_avatar_hash(content_bytes)
        if phash:
            result["avatar_hash"] = phash
    else:
        return {}

    return result


def is_binary_content(content_type: str, url: str) -> bool:
    """Check if a URL or content-type indicates a binary (non-HTML) file."""
    ct = (content_type or "").lower()
    binary_types = ["application/pdf", "image/jpeg", "image/png", "image/tiff",
                    "image/webp", "image/gif", "application/octet-stream"]

    if any(bt in ct for bt in binary_types):
        return True

    binary_extensions = (".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".webp", ".gif", ".bmp")
    if url.lower().split("?")[0].endswith(binary_extensions):
        return True

    return False
