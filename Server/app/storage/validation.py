"""Server-side validation for uploaded meeting recordings.

We deliberately don't trust the client-supplied `Content-Type` header or
file extension alone -- both are trivial to spoof. Instead we sniff the
first bytes of the file for known container/format signatures.
"""

ALLOWED_EXTENSIONS = {
    ".wav", ".mp3", ".mp4", ".m4a", ".ogg", ".oga", ".opus",
    ".flac", ".webm", ".mov", ".mkv", ".aac",
}

SNIFF_BYTES = 32


def has_allowed_extension(filename: str) -> bool:
    lowered = filename.lower()
    return any(lowered.endswith(ext) for ext in ALLOWED_EXTENSIONS)


def sniff_media_signature(header: bytes) -> bool:
    """Best-effort magic-byte check for common audio/video container formats."""
    if len(header) < 4:
        return False

    # WAV: "RIFF"....{"WAVE"}
    if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return True

    # MP3 with an ID3 tag
    if header[:3] == b"ID3":
        return True

    # Bare MP3 frame sync (no ID3 tag): 11111111 111xxxxx
    if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return True

    # ISO base media (MP4 / M4A / MOV): box type "ftyp" at offset 4
    if header[4:8] == b"ftyp":
        return True

    # WebM / MKV (EBML header)
    if header[:4] == b"\x1a\x45\xdf\xa3":
        return True

    # OGG / Opus
    if header[:4] == b"OggS":
        return True

    # FLAC
    if header[:4] == b"fLaC":
        return True

    # ADTS raw AAC
    if header[0] == 0xFF and (header[1] & 0xF6) == 0xF0:
        return True

    return False
