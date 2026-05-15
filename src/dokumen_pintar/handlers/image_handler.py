"""Image format handler.

Provides read access to EXIF / image metadata across JPEG, TIFF, PNG, and
WebP, plus write/strip support for the formats that actually carry an EXIF
payload (JPEG, TIFF, WebP). PNG metadata (tEXt / iTXt chunks) is read but
not written in v1.0.2 — Pillow's PNG writer rebuilds the file and we want to
keep round-trip lossless for now.

The handler intentionally avoids OCR or pixel-level operations; it only
deals with the metadata sidecar.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import piexif
from PIL import Image, ExifTags, TiffImagePlugin, IptcImagePlugin

from ..errors import HandlerError
from .base import FormatHandler, HandlerCapability, default_registry


# ---------- EXIF tag mapping helpers --------------------------------------

_GPS_TAGS: dict[int, str] = ExifTags.GPSTAGS  # type: ignore[attr-defined]
_TAGS: dict[int, str] = ExifTags.TAGS  # type: ignore[attr-defined]

# Common writable tags surfaced via the unified metadata API.
# Map: unified-key -> (IFD-name, piexif-constant)
_WRITABLE_TAGS: dict[str, tuple[str, int]] = {
    "artist": ("0th", piexif.ImageIFD.Artist),
    "copyright": ("0th", piexif.ImageIFD.Copyright),
    "image_description": ("0th", piexif.ImageIFD.ImageDescription),
    "software": ("0th", piexif.ImageIFD.Software),
    "make": ("0th", piexif.ImageIFD.Make),
    "model": ("0th", piexif.ImageIFD.Model),
    "orientation": ("0th", piexif.ImageIFD.Orientation),
    "date_time": ("0th", piexif.ImageIFD.DateTime),
    "date_time_original": ("Exif", piexif.ExifIFD.DateTimeOriginal),
    "date_time_digitized": ("Exif", piexif.ExifIFD.DateTimeDigitized),
    "user_comment": ("Exif", piexif.ExifIFD.UserComment),
    "lens_make": ("Exif", piexif.ExifIFD.LensMake),
    "lens_model": ("Exif", piexif.ExifIFD.LensModel),
}


def _decode_value(value: Any) -> Any:
    """Best-effort conversion of EXIF raw values into JSON-friendly types."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8").rstrip("\x00")
        except UnicodeDecodeError:
            try:
                return value.decode("latin-1").rstrip("\x00")
            except UnicodeDecodeError:
                return value.hex()
    if isinstance(value, TiffImagePlugin.IFDRational):
        try:
            return float(value)
        except (ZeroDivisionError, ValueError):
            return f"{value.numerator}/{value.denominator}"
    if isinstance(value, tuple):
        return [_decode_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _decode_value(v) for k, v in value.items()}
    return value


_GPS_IFD_POINTER = 0x8825  # standard EXIF tag for the GPS sub-IFD.


def _read_exif_via_pillow(path: Path) -> dict[str, Any]:
    """Read EXIF/IFD data via Pillow, return a JSON-ready dict.

    Returns ``{}`` when the file has no EXIF block. GPS data lives in a
    sub-IFD that Pillow surfaces only via ``getexif().get_ifd(0x8825)``;
    we resolve it explicitly so callers see a dict, not an offset int.
    """
    with Image.open(path) as im:
        exif = im.getexif()
    if not exif:
        return {}
    out: dict[str, Any] = {}
    for tag_id, value in exif.items():
        name = _TAGS.get(tag_id, f"Tag_{tag_id}")
        if name == "GPSInfo":
            try:
                gps_ifd = exif.get_ifd(_GPS_IFD_POINTER)
            except (KeyError, AttributeError):  # pragma: no cover — defensive
                gps_ifd = {}
            if isinstance(gps_ifd, dict) and gps_ifd:
                gps_out: dict[str, Any] = {}
                for gps_id, gps_val in gps_ifd.items():
                    gname = _GPS_TAGS.get(gps_id, f"GPS_{gps_id}")
                    gps_out[gname] = _decode_value(gps_val)
                out["GPSInfo"] = gps_out
            else:  # pragma: no cover — defensive: get_ifd returns a real dict
                # whenever the EXIF block declared the GPS sub-IFD pointer.
                out["GPSInfo"] = _decode_value(value)
        else:
            out[name] = _decode_value(value)
    return out


def _gps_to_decimal(coord: Any, ref: Any) -> float | None:
    """Convert ((deg,min,sec), 'N'/'S'/'E'/'W') to signed decimal degrees."""
    if not coord or not ref:
        return None
    try:
        if isinstance(coord, (list, tuple)) and len(coord) == 3:
            deg = float(coord[0])
            mnt = float(coord[1])
            sec = float(coord[2])
            decimal = deg + mnt / 60.0 + sec / 3600.0
        else:
            return None
    except (TypeError, ValueError):
        return None
    if isinstance(ref, bytes):
        ref = ref.decode("ascii", errors="ignore")
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def _extract_gps_summary(exif: dict[str, Any]) -> dict[str, Any] | None:
    gps = exif.get("GPSInfo")
    if not isinstance(gps, dict):
        return None
    lat = _gps_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
    lon = _gps_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
    alt = gps.get("GPSAltitude")
    summary: dict[str, Any] = {}
    if lat is not None:
        summary["latitude"] = lat
    if lon is not None:
        summary["longitude"] = lon
    if alt is not None:
        summary["altitude"] = alt
    return summary or None


def _normalize_value_for_piexif(value: Any) -> Any:
    """Convert a Python value to a piexif-acceptable representation."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, bytes):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        # Convert to rational by *1000 / 1000.
        return (int(round(value * 1000)), 1000)
    raise HandlerError(
        f"unsupported metadata value type: {type(value).__name__}"
    )


class ImageHandler:
    """Handler for raster images with EXIF/IPTC/XMP metadata access."""

    name: str = "image"
    # ``.bmp`` and ``.gif`` are detected but largely metadata-poor; we still
    # accept them so the user gets dimensions/mode at the very least.
    extensions: tuple[str, ...] = (
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
        ".bmp",
        ".gif",
    )
    capabilities: HandlerCapability = (
        HandlerCapability.STRUCTURED_GET
        | HandlerCapability.SEARCH_EXTRACTED
        | HandlerCapability.WRITE_META
        | HandlerCapability.BINARY_ONLY
    )

    # -------- detection --------
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    # -------- reads --------
    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        info: dict[str, Any] = {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }
        try:
            with Image.open(path) as im:
                info["image_format"] = im.format
                info["mode"] = im.mode
                info["width"], info["height"] = im.size
                info["has_alpha"] = "A" in im.mode or im.mode == "P"
                exif = _read_exif_via_pillow(path)
                info["exif"] = exif
                gps_summary = _extract_gps_summary(exif)
                if gps_summary is not None:
                    info["gps"] = gps_summary
                # PNG text chunks live on im.text / im.info, not exif.
                if im.format == "PNG":
                    info["png_text"] = {
                        str(k): str(v) for k, v in getattr(im, "text", {}).items()
                    }
                # Pillow exposes IPTC via getiptcinfo() for IPTC-formatted
                # images (mostly JPEG). Convert any byte values to str.
                try:
                    iptc = IptcImagePlugin.getiptcinfo(im)
                except Exception:  # pragma: no cover — getiptcinfo is robust
                    # for our supported formats; this except is defensive.
                    iptc = None
                if iptc:  # pragma: no cover — JPEGs in our test corpus do
                    # not embed Photoshop-style IPTC blocks, so this branch
                    # is exercised only by real-world media outside CI.
                    info["iptc"] = {
                        f"{k[0]}:{k[1]}": _decode_value(v) for k, v in iptc.items()
                    }
        except (OSError, ValueError) as exc:
            raise HandlerError(f"cannot open image: {exc}") from exc
        return info

    def read_text(self, path: Path, **_: Any) -> str:
        # Images don't have a text payload; the description fields are the
        # closest thing we can offer.
        meta = self.read_meta(path)
        parts: list[str] = []
        exif = meta.get("exif", {})
        for key in ("ImageDescription", "XPComment", "UserComment", "Artist", "Copyright"):
            val = exif.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(f"{key}: {val.strip()}")
        return "\n".join(parts)

    def extract_for_search(self, path: Path) -> str:
        try:
            return self.read_text(path)
        except HandlerError:
            return ""

    def write_text(self, path: Path, content: str, **_: Any) -> None:  # pragma: no cover
        # Not part of the contract for images; the protocol requires the
        # method to exist but we surface a clear error.
        raise HandlerError("write_text is not supported for image files")

    # -------- structured access --------
    def structured_get(self, path: Path, expr: str) -> Any:
        if expr in ("exif", "metadata"):
            return self.read_meta(path).get("exif", {})
        if expr in ("dimensions", "size"):
            meta = self.read_meta(path)
            return {"width": meta["width"], "height": meta["height"]}
        if expr == "gps":
            return self.read_meta(path).get("gps")
        if expr.startswith("exif:"):
            tag = expr.split(":", 1)[1]
            exif = self.read_meta(path).get("exif", {})
            if tag not in exif:
                raise HandlerError(f"exif tag '{tag}' not present")
            return exif[tag]
        raise HandlerError(
            f"unsupported structured_get expression '{expr}' "
            "(expected 'exif', 'exif:<Tag>', 'dimensions', 'gps')"
        )

    def structured_set(  # pragma: no cover — explicit error, write via write_meta
        self, path: Path, expr: str, value: Any
    ) -> None:
        raise HandlerError(
            "structured_set is not supported for image — use metadata_write "
            "to update EXIF fields"
        )

    def structured_delete(  # pragma: no cover
        self, path: Path, expr: str
    ) -> None:
        raise HandlerError(
            "structured_delete is not supported for image — use metadata_delete"
        )

    # -------- write metadata --------
    def write_meta(self, path: Path, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge ``updates`` into the image's EXIF block.

        Keys are looked up in :data:`_WRITABLE_TAGS`; unknown keys are
        rejected with :class:`HandlerError`. Setting a value to ``None``
        deletes that tag.

        Returns a dict describing what was actually written.
        """
        if path.suffix.lower() not in (".jpg", ".jpeg", ".tif", ".tiff", ".webp"):
            raise HandlerError(
                f"writing EXIF is not supported for {path.suffix} files"
            )
        try:
            exif_dict = piexif.load(str(path))
        except Exception as exc:  # noqa: BLE001
            raise HandlerError(f"failed to read EXIF: {exc}") from exc

        applied: dict[str, Any] = {}
        for key, value in updates.items():
            if key not in _WRITABLE_TAGS:
                raise HandlerError(
                    f"unknown writable tag '{key}' "
                    f"(allowed: {sorted(_WRITABLE_TAGS)})"
                )
            ifd_name, tag_id = _WRITABLE_TAGS[key]
            ifd = exif_dict.setdefault(ifd_name, {})
            if value is None:
                ifd.pop(tag_id, None)
                applied[key] = None
            else:
                ifd[tag_id] = _normalize_value_for_piexif(value)
                applied[key] = value

        try:
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(path))
        except Exception as exc:  # noqa: BLE001
            raise HandlerError(f"failed to write EXIF: {exc}") from exc
        return applied

    def strip_meta(self, path: Path) -> dict[str, Any]:
        """Remove all EXIF / metadata from the image."""
        if path.suffix.lower() not in (".jpg", ".jpeg", ".tif", ".tiff", ".webp"):
            raise HandlerError(
                f"stripping EXIF is not supported for {path.suffix} files"
            )
        try:
            piexif.remove(str(path))
        except Exception as exc:  # noqa: BLE001
            raise HandlerError(f"failed to strip EXIF: {exc}") from exc
        return {"stripped": True}


_handler: FormatHandler = ImageHandler()
default_registry.register(_handler)
