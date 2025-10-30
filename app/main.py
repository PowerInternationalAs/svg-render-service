"""HTTP entrypoint for the SVG render Cloud Run service."""

from __future__ import annotations

import io
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple
from urllib.parse import urlparse

import requests
from cairosvg import svg2png
from cairosvg.parser import Tree
from flask import Flask, jsonify, request
from google.api_core.exceptions import GoogleAPIError
from google.cloud import storage

from .config import get_settings


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()

if not settings.api_key:
    raise RuntimeError("API_KEY environment variable must be set for the service to start.")

storage_client = storage.Client()

API_KEY_HEADER = "X-API-Key"
OBJECT_PREFIX = "renders"

_SVG_UNIT_TO_PX = {
    "": 1.0,
    "px": 1.0,
    "pt": 96 / 72,  # CSS points
    "pc": 16.0,
    "mm": 96 / 25.4,
    "cm": 96 / 2.54,
    "in": 96.0,
}
_LENGTH_RE = re.compile(r"^\s*([-+]?\d*\.?\d+)")

app = Flask(__name__)


def _is_authorized(provided_key: str | None) -> bool:
    return bool(provided_key) and provided_key == settings.api_key


def _validate_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _fetch_svg(svg_url: str) -> bytes:
    try:
        with requests.get(
            svg_url,
            timeout=settings.request_timeout_seconds,
            stream=True,
        ) as response:
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > settings.max_svg_bytes:
                raise ValueError("SVG exceeds maximum allowed size.")

            buffer = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                buffer.write(chunk)
                if buffer.tell() > settings.max_svg_bytes:
                    raise ValueError("SVG exceeds maximum allowed size.")

        svg_bytes = buffer.getvalue()
        if not svg_bytes.strip():
            raise ValueError("SVG document is empty.")

        return svg_bytes
    except requests.RequestException as exc:
        raise ValueError(f"Unable to download SVG: {exc}") from exc


def _compute_scale(width: float, height: float) -> Tuple[int, int]:
    if width <= 0 or height <= 0:
        width = float(settings.min_output_width)
        height = float(settings.min_output_width)

    scale = 1.0

    if width < settings.min_output_width:
        scale = max(scale, settings.min_output_width / width)

    if width * scale > settings.max_output_width:
        scale = settings.max_output_width / width

    if height * scale > settings.max_output_height:
        scale = settings.max_output_height / height

    scaled_width = max(1, int(round(width * scale)))
    scaled_height = max(1, int(round(height * scale)))

    return scaled_width, scaled_height


def _parse_svg_length(raw_value: str | None) -> float:
    if not raw_value:
        return 0.0

    match = _LENGTH_RE.match(raw_value)
    if not match:
        return 0.0

    value = float(match.group(1))
    unit = raw_value[match.end():].strip().lower()

    if unit.endswith("%"):
        return 0.0

    if unit in _SVG_UNIT_TO_PX:
        return value * _SVG_UNIT_TO_PX[unit]

    return value


def _extract_svg_dimensions(tree: Tree) -> Tuple[float, float]:
    width = _parse_svg_length(tree.get("width"))
    height = _parse_svg_length(tree.get("height"))

    view_box = tree.get("viewBox")
    if view_box:
        components = [part for part in re.split(r"[\s,]+", view_box.strip()) if part]
        if len(components) == 4:
            _, _, viewbox_width, viewbox_height = components
            if width <= 0:
                width = _parse_svg_length(viewbox_width)
            if height <= 0:
                height = _parse_svg_length(viewbox_height)

    return width, height


def _convert_svg_to_png(svg_bytes: bytes) -> Tuple[bytes, int, int]:
    tree = Tree(bytestring=svg_bytes)

    width, height = _extract_svg_dimensions(tree)

    target_width, target_height = _compute_scale(width, height)

    png_bytes = svg2png(
        bytestring=svg_bytes,
        output_width=target_width,
        output_height=target_height,
    )

    return png_bytes, target_width, target_height


def _upload_png(png_bytes: bytes) -> Tuple[str, str]:
    blob_name = f"{OBJECT_PREFIX}/{uuid.uuid4().hex}.png"
    bucket = storage_client.bucket(settings.bucket_name)
    blob = bucket.blob(blob_name)

    blob.upload_from_string(png_bytes, content_type="image/png")

    expiration = timedelta(seconds=settings.signed_url_ttl_seconds)
    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=expiration,
        method="GET",
    )

    return blob_name, signed_url


def _prune_old_files(now: datetime) -> int:
    bucket = storage_client.bucket(settings.bucket_name)
    cutoff = now - timedelta(seconds=settings.prune_after_seconds)
    deleted = 0

    try:
        for blob in bucket.list_blobs(prefix=OBJECT_PREFIX):
            if not blob.time_created:
                continue
            if blob.time_created < cutoff:
                logger.info("Pruning stale object %s", blob.name)
                blob.delete()
                deleted += 1
    except GoogleAPIError as exc:
        logger.warning("Failed to prune old files: %s", exc)

    return deleted


@app.route("/render", methods=["POST"])
def render_svg() -> tuple:
    provided_key = request.headers.get(API_KEY_HEADER)
    if not _is_authorized(provided_key):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    svg_url = payload.get("svg_url")

    if not svg_url or not isinstance(svg_url, str) or not _validate_url(svg_url):
        return jsonify({"error": "svg_url must be a valid HTTP(S) URL."}), 400

    try:
        svg_bytes = _fetch_svg(svg_url)
        png_bytes, width, height = _convert_svg_to_png(svg_bytes)
        blob_name, signed_url = _upload_png(png_bytes)
    except ValueError as exc:
        logger.warning("Client error: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except (GoogleAPIError, OSError) as exc:
        logger.exception("Rendering failed: %s", exc)
        return jsonify({"error": "Failed to render SVG."}), 500

    now = datetime.now(timezone.utc)
    deleted = _prune_old_files(now)

    response = {
        "png_url": signed_url,
        "object_name": blob_name,
        "dimensions": {"width": width, "height": height},
        "pruned_files": deleted,
    }

    return jsonify(response), 200


@app.route("/healthz", methods=["GET"])
def health_check() -> tuple:
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
