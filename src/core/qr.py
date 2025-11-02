"""QR code utilities."""

from __future__ import annotations

import io
from typing import BinaryIO

import qrcode


def qris_to_image(data: str) -> BinaryIO:
    """Generate QR code image bytes from QRIS string."""
    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
