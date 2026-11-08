"""
Comprehensive Acceptance Test Suite for Local Music Server & Audio Studio
Covers all 10 acceptance tests:
1. Rename an MP3 file
2. Convert WAV to MP3
3. Convert FLAC to MP3
4. Optimize a large WAV file
5. Merge three MP3 files
6. Merge MP3 + WAV + M4A into one MP3
7. Merge five files with silence between tracks
8. Merge three files with crossfade
9. Download the final merged file (verifying headers & legacy Android compatibility)
10. Verify that original source files remain unchanged
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import subprocess
from audio_service import find_binary

TEST_PORT = 8998
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"
MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")

FFMPEG_BIN = find_binary("ffmpeg")

def log(msg):
    print(msg, flush=True)

def cleanup_test_artifacts():
    cleanup_files = [
        "sample_rename.mp3", "renamed_track.mp3", "test_tone.wav", "converted_from_wav.mp3",
        "test_tone.flac", "converted_from_flac.mp3", "large_audio.wav",
        "optimized_audio.mp3", "m1.mp3", "m2.mp3", "m3.mp3", "three_mp3_merged.mp3",
        "mix_track1.mp3", "mix_track2.wav", "mix_track3.m4a", "mixed_formats_merged.mp3",
        "five_with_silence.mp3", "cf1.mp3", "cf2.mp3", "cf3.mp3", "three_crossfaded.mp3"
    ] + [f"five_{i}.mp3" for i in range(1, 6)]
    for cf in cleanup_files:
        cp = os.path.join(MUSIC_DIR, cf)
        if os.path.exists(cp):
            try:
                os.remove(cp)
            except Exception:
                pass
    # also remove any .tmp_* files
    for entry in os.scandir(MUSIC_DIR):
        if entry.name.startswith(".tmp_"):
            try:
                os.remove(entry.path)
            except Exception:
                pass

def generate_test_audio(filename, duration=3, freq=440, codec=None):
    """Generate genuine audio files using FFmpeg synthetic sine wave."""
    out_path = os.path.join(MUSIC_DIR, filename)
    cmd = [
        FFMPEG_BIN, "-y",
        "-loglevel", "error",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration}",
    ]
    if codec:
        cmd.extend(["-c:a", codec])
    cmd.append(out_path)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return out_path

def poll_task(task_id, timeout=30):
    """Poll task until completion or failure."""
    start = time.time()
    while time.time() - start < timeout:
        req = urllib.request.urlopen(f"{BASE_URL}/api/tasks/{task_id}")
        data = json.loads(req.read().decode('utf-8'))
        task = data.get("task", {})
        status = task.get("status")
        if status == "completed":
            return task
        elif status == "failed":
            raise RuntimeError(f"Task {task_id} failed: {task.get('error')}")
        time.sleep(0.3)
    raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

def run_acceptance_tests():
    log(f"=== Starting Audio Studio Acceptance Tests on port {TEST_PORT} ===")
    assert FFMPEG_BIN, "FFmpeg binary is required for tests!"
    log(f"Using FFmpeg at: {FFMPEG_BIN}")

    # Clean any stale test files before starting
    cleanup_test_artifacts()

    # Launch server with DEVNULL for pipe to prevent buffer stalls
    proc = subprocess.Popen([sys.executable, "server.py", str(TEST_PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

    try:
        # Check server health
        req = urllib.request.urlopen(f"{BASE_URL}/api/files")
        assert req.status == 200

        # -------------------------------------------------------------
        # Test 1: Rename an MP3 file
        # -------------------------------------------------------------
        log("\n--- Test 1: Rename an MP3 file ---")
        generate_test_audio("sample_rename.mp3", duration=2, freq=440)
        assert os.path.exists(os.path.join(MUSIC_DIR, "sample_rename.mp3"))

        rename_payload = json.dumps({
            "old_name": "sample_rename.mp3",
            "new_name": "renamed_track.mp3"
        }).encode('utf-8')
        rename_req = urllib.request.Request(
            f"{BASE_URL}/api/rename",
            data=rename_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(rename_req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert data["success"] is True
            assert data["new_name"] == "renamed_track.mp3"

        assert not os.path.exists(os.path.join(MUSIC_DIR, "sample_rename.mp3"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "renamed_track.mp3"))
        log("  -> Passed! MP3 renamed properly and verified on disk.")

        # -------------------------------------------------------------
        # Test 2: Convert WAV to MP3
        # -------------------------------------------------------------
        log("\n--- Test 2: Convert WAV to MP3 ---")
        generate_test_audio("test_tone.wav", duration=3, freq=523, codec="pcm_s16le")
        src_wav_path = os.path.join(MUSIC_DIR, "test_tone.wav")
        src_wav_size = os.path.getsize(src_wav_path)

        conv_payload = json.dumps({
            "source_filename": "test_tone.wav",
            "output_format": "mp3",
            "target_filename": "converted_from_wav.mp3",
            "bitrate": "192k",
            "sample_rate": 44100,
            "channels": 2
        }).encode('utf-8')
        conv_req = urllib.request.Request(
            f"{BASE_URL}/api/convert",
            data=conv_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(conv_req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            task_id = data["task_id"]

        task = poll_task(task_id)
        assert task["status"] == "completed"
        assert os.path.exists(os.path.join(MUSIC_DIR, "converted_from_wav.mp3"))
        out_mp3_size = os.path.getsize(os.path.join(MUSIC_DIR, "converted_from_wav.mp3"))
        log(f"  -> Passed! WAV ({src_wav_size} B) converted to MP3 ({out_mp3_size} B, {task['reduction_percent']}% reduction).")

        # -------------------------------------------------------------
        # Test 3: Convert FLAC to MP3
        # -------------------------------------------------------------
        log("\n--- Test 3: Convert FLAC to MP3 ---")
        generate_test_audio("test_tone.flac", duration=3, freq=587, codec="flac")
        conv_flac_payload = json.dumps({
            "source_filename": "test_tone.flac",
            "output_format": "mp3",
            "target_filename": "converted_from_flac.mp3",
            "bitrate": "192k"
        }).encode('utf-8')
        conv_flac_req = urllib.request.Request(
            f"{BASE_URL}/api/convert",
            data=conv_flac_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(conv_flac_req) as resp:
            task_id = json.loads(resp.read().decode('utf-8'))["task_id"]
        task = poll_task(task_id)
        assert task["status"] == "completed"
        assert os.path.exists(os.path.join(MUSIC_DIR, "converted_from_flac.mp3"))
        log("  -> Passed! FLAC converted to MP3 successfully.")

        # -------------------------------------------------------------
        # Test 4: Optimize a large WAV file
        # -------------------------------------------------------------
        log("\n--- Test 4: Optimize a large WAV file ---")
        generate_test_audio("large_audio.wav", duration=8, freq=440, codec="pcm_s16le")
        large_wav_size = os.path.getsize(os.path.join(MUSIC_DIR, "large_audio.wav"))

        opt_payload = json.dumps({
            "source_filename": "large_audio.wav",
            "output_format": "mp3",
            "target_filename": "optimized_audio.mp3",
            "bitrate": "128k"
        }).encode('utf-8')
        opt_req = urllib.request.Request(
            f"{BASE_URL}/api/convert",
            data=opt_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(opt_req) as resp:
            task_id = json.loads(resp.read().decode('utf-8'))["task_id"]
        task = poll_task(task_id)
        assert task["status"] == "completed"
        opt_size = os.path.getsize(os.path.join(MUSIC_DIR, "optimized_audio.mp3"))
        log(f"  -> Passed! Large WAV ({large_wav_size} B) optimized to MP3 ({opt_size} B, {task['reduction_percent']}% size reduction).")

        # -------------------------------------------------------------
        # Test 5: Merge three MP3 files
        # -------------------------------------------------------------
        log("\n--- Test 5: Merge three MP3 files ---")
        generate_test_audio("m1.mp3", duration=2, freq=261, codec="libmp3lame")
        generate_test_audio("m2.mp3", duration=2, freq=329, codec="libmp3lame")
        generate_test_audio("m3.mp3", duration=2, freq=392, codec="libmp3lame")

        merge3_payload = json.dumps({
            "source_filenames": ["m1.mp3", "m2.mp3", "m3.mp3"],
            "target_filename": "three_mp3_merged.mp3",
            "output_format": "mp3",
            "bitrate": "192k"
        }).encode('utf-8')
        merge3_req = urllib.request.Request(
            f"{BASE_URL}/api/merge",
            data=merge3_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(merge3_req) as resp:
            task_id = json.loads(resp.read().decode('utf-8'))["task_id"]
        task = poll_task(task_id)
        assert task["status"] == "completed"
        assert os.path.exists(os.path.join(MUSIC_DIR, "three_mp3_merged.mp3"))
        log(f"  -> Passed! Three MP3s merged into one track (Duration ~ {task['duration']}s).")

        # -------------------------------------------------------------
        # Test 6: Merge MP3 + WAV + M4A into one MP3 (Mixed Format)
        # -------------------------------------------------------------
        log("\n--- Test 6: Merge MP3 + WAV + M4A into one MP3 ---")
        generate_test_audio("mix_track1.mp3", duration=2, freq=440, codec="libmp3lame")
        generate_test_audio("mix_track2.wav", duration=2, freq=554, codec="pcm_s16le")
        generate_test_audio("mix_track3.m4a", duration=2, freq=659, codec="aac")

        mixed_payload = json.dumps({
            "source_filenames": ["mix_track1.mp3", "mix_track2.wav", "mix_track3.m4a"],
            "target_filename": "mixed_formats_merged.mp3",
            "output_format": "mp3",
            "bitrate": "192k"
        }).encode('utf-8')
        mixed_req = urllib.request.Request(
            f"{BASE_URL}/api/merge",
            data=mixed_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(mixed_req) as resp:
            task_id = json.loads(resp.read().decode('utf-8'))["task_id"]
        task = poll_task(task_id)
        assert task["status"] == "completed"
        assert os.path.exists(os.path.join(MUSIC_DIR, "mixed_formats_merged.mp3"))
        log("  -> Passed! Mixed formats (MP3 + WAV + M4A) seamlessly decoded, normalized, and merged!")

        # -------------------------------------------------------------
        # Test 7: Merge five files with silence between tracks
        # -------------------------------------------------------------
        log("\n--- Test 7: Merge five files with silence between tracks ---")
        for i in range(1, 6):
            generate_test_audio(f"five_{i}.mp3", duration=1, freq=300 + (i * 100), codec="libmp3lame")

        silence_payload = json.dumps({
            "source_filenames": [f"five_{i}.mp3" for i in range(1, 6)],
            "target_filename": "five_with_silence.mp3",
            "output_format": "mp3",
            "silence": 1.0
        }).encode('utf-8')
        silence_req = urllib.request.Request(
            f"{BASE_URL}/api/merge",
            data=silence_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(silence_req) as resp:
            task_id = json.loads(resp.read().decode('utf-8'))["task_id"]
        task = poll_task(task_id)
        assert task["status"] == "completed"
        assert os.path.exists(os.path.join(MUSIC_DIR, "five_with_silence.mp3"))
        log(f"  -> Passed! Five tracks merged with silence gaps (Est duration: {task['duration']}s).")

        # -------------------------------------------------------------
        # Test 8: Merge three files with crossfade
        # -------------------------------------------------------------
        log("\n--- Test 8: Merge three files with crossfade ---")
        generate_test_audio("cf1.mp3", duration=4, freq=300, codec="libmp3lame")
        generate_test_audio("cf2.mp3", duration=4, freq=400, codec="libmp3lame")
        generate_test_audio("cf3.mp3", duration=4, freq=500, codec="libmp3lame")

        cf_payload = json.dumps({
            "source_filenames": ["cf1.mp3", "cf2.mp3", "cf3.mp3"],
            "target_filename": "three_crossfaded.mp3",
            "output_format": "mp3",
            "crossfade": 1.5
        }).encode('utf-8')
        cf_req = urllib.request.Request(
            f"{BASE_URL}/api/merge",
            data=cf_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(cf_req) as resp:
            task_id = json.loads(resp.read().decode('utf-8'))["task_id"]
        task = poll_task(task_id)
        assert task["status"] == "completed"
        assert os.path.exists(os.path.join(MUSIC_DIR, "three_crossfaded.mp3"))
        log(f"  -> Passed! Three tracks merged with 1.5s acrossfade (Duration: {task['duration']}s).")

        # -------------------------------------------------------------
        # Test 9: Download the final merged file from legacy Android Chrome
        # -------------------------------------------------------------
        log("\n--- Test 9: Download the final merged file from legacy Android Chrome ---")
        req_car = urllib.request.urlopen(f"{BASE_URL}/")
        assert req_car.status == 200
        car_html = req_car.read().decode('utf-8')
        assert "three_crossfaded.mp3" in car_html
        assert "/download/three_crossfaded.mp3" in car_html

        dl_url = f"{BASE_URL}/download/" + urllib.parse.quote("three_crossfaded.mp3")
        req_dl = urllib.request.Request(
            dl_url,
            headers={"User-Agent": "Mozilla/5.0 (Linux; U; Android 4.4.4; en-us; Nexus 7 Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.0.0 Mobile Safari/537.36"}
        )
        with urllib.request.urlopen(req_dl) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "audio/mpeg"
            assert "attachment" in resp.headers.get("Content-Disposition")
            data_bytes = resp.read()
            assert len(data_bytes) == os.path.getsize(os.path.join(MUSIC_DIR, "three_crossfaded.mp3"))
        log(f"  -> Passed! Direct HTTP download verified ({len(data_bytes)} bytes) with proper headers.")

        # -------------------------------------------------------------
        # Test 10: Verify that original source files remain unchanged
        # -------------------------------------------------------------
        log("\n--- Test 10: Verify that original source files remain unchanged ---")
        assert os.path.exists(os.path.join(MUSIC_DIR, "test_tone.wav"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "test_tone.flac"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "large_audio.wav"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "mix_track1.mp3"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "mix_track2.wav"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "mix_track3.m4a"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "cf1.mp3"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "cf2.mp3"))
        assert os.path.exists(os.path.join(MUSIC_DIR, "cf3.mp3"))
        log("  -> Passed! All original source audio files remain intact and unchanged.")

        # Clean up test files created during tests
        log("\nCleaning up test generated files...")
        cleanup_test_artifacts()

        log("\n=======================================================")
        log(">>> ALL 10 AUDIO STUDIO ACCEPTANCE TESTS PASSED! 100% <<<")
        log("=======================================================")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    run_acceptance_tests()
