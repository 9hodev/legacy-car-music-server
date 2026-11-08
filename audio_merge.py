"""
Audio Merge Studio Module
Constructs FFmpeg filter_complex chains to cleanly concatenate and crossfade mixed-format audio tracks.
"""

import os
from audio_convert import (
    SUPPORTED_INPUT_EXTS,
    SUPPORTED_OUTPUT_EXTS,
    LOSSY_EXTS,
    CODEC_MAP,
    VALID_BITRATES,
    VALID_SAMPLE_RATES
)


def build_merge_command(ffmpeg_bin, input_paths, output_path, options, track_durations=None):
    """
    Construct safe argument list for merging multiple audio files with mixed formats.
    options = {
        'output_format': 'mp3',
        'bitrate': '192k',
        'sample_rate': 44100,
        'channels': 2,
        'crossfade': 0.0,
        'silence': 0.0
    }
    """
    if len(input_paths) < 2:
        raise ValueError("At least two audio tracks are required to merge.")

    out_ext = os.path.splitext(output_path)[1].lower()
    if out_ext not in SUPPORTED_OUTPUT_EXTS:
        raise ValueError(f"Unsupported output format: {out_ext}")

    sample_rate = int(options.get("sample_rate", 44100))
    if sample_rate not in VALID_SAMPLE_RATES:
        sample_rate = 44100

    channels = int(options.get("channels", 2))
    channel_layout = "stereo" if channels == 2 else "mono"

    crossfade = float(options.get("crossfade", 0.0))
    silence = float(options.get("silence", 0.0))

    # Validate crossfade against track durations if provided
    if crossfade > 0 and track_durations:
        min_dur = min(track_durations)
        if crossfade >= min_dur:
            crossfade = max(0.5, round(min_dur / 2.0, 1))

    cmd = [ffmpeg_bin, "-y", "-loglevel", "error"]

    # Add each input file
    for p in input_paths:
        ext = os.path.splitext(p)[1].lower()
        if ext not in SUPPORTED_INPUT_EXTS:
            raise ValueError(f"Input file '{os.path.basename(p)}' has unsupported format: {ext}")
        cmd.extend(["-i", p])

    filter_chains = []
    n = len(input_paths)

    if crossfade > 0:
        # Crossfade using chained acrossfade filters
        # Step 1: Normalize all inputs to same sample rate and channel layout
        for i in range(n):
            filter_chains.append(f"[{i}:a]aformat=sample_rates={sample_rate}:channel_layouts={channel_layout}[a{i}]")

        # Step 2: Chain acrossfade
        current_label = "a0"
        for i in range(1, n):
            next_label = f"a{i}"
            out_label = f"cf{i}" if i < n - 1 else "outa"
            filter_chains.append(
                f"[{current_label}][{next_label}]acrossfade=d={crossfade}:c1=tri:c2=tri[{out_label}]"
            )
            current_label = out_label

    elif silence > 0:
        # Silence padding between tracks using apad on each track except the last
        for i in range(n):
            if i < n - 1:
                filter_chains.append(
                    f"[{i}:a]aformat=sample_rates={sample_rate}:channel_layouts={channel_layout},apad=pad_dur={silence}[a{i}]"
                )
            else:
                filter_chains.append(
                    f"[{i}:a]aformat=sample_rates={sample_rate}:channel_layouts={channel_layout}[a{i}]"
                )

        concat_inputs = "".join([f"[a{i}]" for i in range(n)])
        filter_chains.append(f"{concat_inputs}concat=n={n}:v=0:a=1[outa]")

    else:
        # Simple clean concatenation
        for i in range(n):
            filter_chains.append(
                f"[{i}:a]aformat=sample_rates={sample_rate}:channel_layouts={channel_layout}[a{i}]"
            )

        concat_inputs = "".join([f"[a{i}]" for i in range(n)])
        filter_chains.append(f"{concat_inputs}concat=n={n}:v=0:a=1[outa]")

    filter_complex = ";".join(filter_chains)

    codec = CODEC_MAP.get(out_ext, "libmp3lame")

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        "-c:a", codec
    ])

    # Bitrate for lossy codecs
    if out_ext in LOSSY_EXTS:
        bitrate = options.get("bitrate", "192k")
        if not bitrate.endswith("k"):
            bitrate = f"{bitrate}k"
        if bitrate not in VALID_BITRATES:
            bitrate = "192k"
        cmd.extend(["-b:a", bitrate])

    cmd.extend([
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-progress", "pipe:1",
        "-nostats",
        output_path
    ])

    return cmd

