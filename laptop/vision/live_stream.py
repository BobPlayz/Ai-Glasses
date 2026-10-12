from __future__ import annotations

"""Local live-video helpers for AI Glasses.

The still-image path remains :func:`ask_image_local`. This module adds a bounded
MJPEG reader and a throttled inference loop for sources that expose an MJPEG URL.
The current XIAO firmware protocol uploads privacy-gated JPEG snapshots; it does
not itself expose an MJPEG server. Do not point this helper at a public URL.
"""

import ipaddress
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from urllib.parse import urlsplit

from laptop.vision.lan_http import open_no_redirect
from laptop.vision.local_vision import VisionError, ask_image_local

MAX_FRAME_BYTES = 8 * 1024 * 1024
DEFAULT_USER_AGENT = "AI-Glasses-Local/1.0"


def _validate_lan_stream_url(url: str) -> None:
    """Restrict live streams to plain HTTP on a private/loopback IP address."""
    parsed = urlsplit(url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise VisionError("Live video must use an HTTP URL on your trusted local network.")
    if parsed.username or parsed.password:
        raise VisionError("Do not embed credentials in a camera URL.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise VisionError("Use the camera's private LAN IP address, not a hostname.") from exc
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise VisionError("Live video is restricted to private or local IP addresses.")
    if parsed.port is None:
        raise VisionError("Include the camera stream's port in the URL.")


def iter_mjpeg_frames(url: str, *, timeout: float = 8.0) -> Iterator[bytes]:
    """Yield JPEG frames from a local multipart/x-mixed-replace MJPEG stream.

    The reader is intentionally bounded: a malformed or oversized frame is
    discarded, and the response is closed as soon as iteration ends.
    """
    _validate_lan_stream_url(url)
    request = urllib.request.Request(
        url,
        headers={"Accept": "multipart/x-mixed-replace, image/jpeg",
                 "User-Agent": DEFAULT_USER_AGENT},
    )
    try:
        response = open_no_redirect(request, timeout=timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VisionError(f"Could not connect to the local camera stream: {exc}") from exc

    with response:
        content_type = response.headers.get("Content-Type", "")
        if "multipart/" not in content_type.lower():
            raise VisionError("Camera URL did not return an MJPEG multipart stream.")

        buffer = bytearray()
        while True:
            chunk = response.read(4096)
            if not chunk:
                return
            buffer.extend(chunk)
            # A stream that never emits a JPEG boundary must not grow forever.
            if len(buffer) > MAX_FRAME_BYTES * 2:
                del buffer[:-MAX_FRAME_BYTES]
            while True:
                start = buffer.find(b"\xff\xd8")
                if start < 0:
                    if len(buffer) > 1:
                        del buffer[:-1]
                    break
                end = buffer.find(b"\xff\xd9", start + 2)
                if end < 0:
                    if start:
                        del buffer[:start]
                    break
                frame = bytes(buffer[start:end + 2])
                del buffer[:end + 2]
                if len(frame) <= MAX_FRAME_BYTES:
                    yield frame


def describe_image(image_bytes: bytes, question: str) -> dict:
    """Describe one uploaded/captured image with the configured local vision model."""
    return ask_image_local(image_bytes, question)


def describe_live_stream(
    url: str,
    question: str,
    on_result: Callable[[dict], None],
    *,
    seconds: float = 20.0,
    inference_interval: float = 2.0,
) -> int:
    """Run bounded, throttled inference on frames from a local MJPEG stream.

    Returns the number of successful descriptions. The callback is invoked once
    per analyzed frame, not once per raw video frame, to avoid saturating a laptop.
    """
    if not 1 <= seconds <= 300:
        raise VisionError("Live analysis duration must be between 1 and 300 seconds.")
    if not 0.5 <= inference_interval <= 30:
        raise VisionError("Inference interval must be between 0.5 and 30 seconds.")

    started = time.monotonic()
    last_inference = 0.0
    count = 0
    for frame in iter_mjpeg_frames(url):
        now = time.monotonic()
        if now - started >= seconds:
            break
        if now - last_inference < inference_interval:
            continue
        result = ask_image_local(frame, question)
        result["source"] = "live_video"
        result["captured_at"] = time.time()
        on_result(result)
        count += 1
        last_inference = time.monotonic()
    return count
