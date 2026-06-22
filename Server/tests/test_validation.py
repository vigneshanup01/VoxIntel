from app.storage.validation import has_allowed_extension, sniff_media_signature
from tests.conftest import wav_bytes


def test_allowed_extension_accepts_known_formats() -> None:
    assert has_allowed_extension("meeting.wav") is True
    assert has_allowed_extension("meeting.MP4") is True
    assert has_allowed_extension("meeting.webm") is True


def test_allowed_extension_rejects_unknown_formats() -> None:
    assert has_allowed_extension("meeting.exe") is False
    assert has_allowed_extension("meeting.txt") is False
    assert has_allowed_extension("meeting") is False


def test_sniff_accepts_wav_signature() -> None:
    assert sniff_media_signature(wav_bytes()[:32]) is True


def test_sniff_accepts_mp3_with_id3_tag() -> None:
    header = b"ID3" + b"\x03\x00\x00\x00\x00\x00\x21" + b"\x00" * 20
    assert sniff_media_signature(header) is True


def test_sniff_accepts_bare_mp3_frame_sync() -> None:
    header = bytes([0xFF, 0xFB, 0x90, 0x44]) + b"\x00" * 20
    assert sniff_media_signature(header) is True


def test_sniff_accepts_mp4_ftyp_box() -> None:
    header = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20
    assert sniff_media_signature(header) is True


def test_sniff_rejects_arbitrary_binary() -> None:
    header = b"This is just plain text, not media" + b"\x00" * 10
    assert sniff_media_signature(header) is False


def test_sniff_rejects_renamed_executable() -> None:
    header = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00" + b"\x00" * 20
    assert sniff_media_signature(header) is False
