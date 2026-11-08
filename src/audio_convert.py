"""
Audio Convert and Optimize Module
Constructs verified, safe FFmpeg command configurations for audio conversion.
"""

import os

SUPPORTED_INPUT_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
SUPPORTED_OUTPUT_EXTS = {".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac"}
LOSSY_EXTS = {".mp3", ".m4a", ".aac", ".ogg", ".opus"}

VALID_BITRATES = {"320k", "256k", "192k", "128k", "96k"}
VALID_SAMPLE_RATES = {44100, 48000}
VALID_CHANNELS = {1: "mono", 2: "stereo"}

CODEC_MAP = {
    ".mp3": "libmp3lame",
    ".m4a": "aac",
    ".aac": "aac",
    ".ogg": "libvorbis",
    ".wav": "pcm_s16le",
    ".flac": "flac",
    ".opus": "libopus"
}


def is_lossy_transcode(in_ext, out_ext):
    """Check if transcoding from lossy to lossy format."""
    return in_ext.lower() in LOSSY_EXTS and out_ext.lower() in LOSSY_EXTS


def build_convert_command(ffmpeg_bin, input_path, output_path, options):
    """
    Construct safe argument list for FFmpeg conversion.
    options = {
        'output_format': 'mp3' / '.mp3',
        'bitrate': '192k',
        'sample_rate': 44100 / None,
        'channels': 2 / 1 / None
    }
    """
    in_ext = os.path.splitext(input_path)[1].lower()
    out_ext = os.path.splitext(output_path)[1].lower()

    if in_ext not in SUPPORTED_INPUT_EXTS:
        raise ValueError(f"Unsupported input format: {in_ext}")
    if out_ext not in SUPPORTED_OUTPUT_EXTS:
        raise ValueError(f"Unsupported output format: {out_ext}")

    codec = CODEC_MAP.get(out_ext, "copy")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-loglevel", "error",
        "-i", input_path,
        "-c:a", codec
    ]

    # Bitrate (only applies to lossy codecs)
    if out_ext in LOSSY_EXTS:
        bitrate = options.get("bitrate", "192k")
        if not bitrate.endswith("k"):
            bitrate = f"{bitrate}k"
        if bitrate in VALID_BITRATES:
            cmd.extend(["-b:a", bitrate])
        else:
            cmd.extend(["-b:a", "192k"])

    # Sample rate
    sample_rate = options.get("sample_rate")
    if sample_rate:
        try:
            sr = int(sample_rate)
            if sr in VALID_SAMPLE_RATES:
                cmd.extend(["-ar", str(sr)])
        except (ValueError, TypeError):
            pass

    # Channels
    channels = options.get("channels")
    if channels:
        try:
            ch = int(channels)
            if ch in [1, 2]:
                cmd.extend(["-ac", str(ch)])
        except (ValueError, TypeError):
            pass

    # Progress reporting to stdout
    cmd.extend([
        "-progress", "pipe:1",
        "-nostats",
        output_path
    ])

    return cmd

