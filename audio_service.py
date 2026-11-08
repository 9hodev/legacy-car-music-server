"""
Audio Service Module
Manages FFmpeg processes, task queues, progress tracking, metadata extraction,
and file locking to protect files currently being converted or merged.
"""

import os
import sys
import json
import time
import uuid
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

from audio_convert import (
    SUPPORTED_INPUT_EXTS,
    SUPPORTED_OUTPUT_EXTS,
    is_lossy_transcode,
    build_convert_command
)
from audio_merge import build_merge_command


def find_binary(name):
    """Find executable in PATH or common directories."""
    path = shutil.which(name)
    if path:
        return path

    # Search common Windows paths if on Windows
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            winget_dir = os.path.join(local_app, "Microsoft", "WinGet", "Packages")
            if os.path.isdir(winget_dir):
                for root, dirs, files in os.walk(winget_dir):
                    if f"{name}.exe" in files:
                        return os.path.join(root, f"{name}.exe")
        for p in [r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"]:
            cand = os.path.join(p, f"{name}.exe")
            if os.path.isfile(cand):
                return cand

    # Search common macOS paths if on Darwin
    if sys.platform == "darwin":
        for p in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            cand = os.path.join(p, name)
            if os.path.isfile(cand):
                return cand

    return None


class AudioService:
    def __init__(self, music_dir, max_workers=2, db_service=None):
        self.music_dir = music_dir
        self.db_service = db_service
        self.ffmpeg_bin = find_binary("ffmpeg")
        self.ffprobe_bin = find_binary("ffprobe")
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        self.tasks = {}
        self.task_lock = threading.Lock()
        self.locked_files = set()
        self.files_lock = threading.Lock()

    def refresh_binaries(self):
        """Re-probe binary paths."""
        self.ffmpeg_bin = find_binary("ffmpeg")
        self.ffprobe_bin = find_binary("ffprobe")
        return bool(self.ffmpeg_bin and self.ffprobe_bin)

    def is_available(self):
        if not (self.ffmpeg_bin and self.ffprobe_bin):
            self.refresh_binaries()
        return bool(self.ffmpeg_bin and self.ffprobe_bin)

    # ------------------------------------------------------------------
    # File Locking
    # ------------------------------------------------------------------
    def is_file_locked(self, filename):
        with self.files_lock:
            return filename in self.locked_files

    def _lock_files(self, filenames):
        with self.files_lock:
            for f in filenames:
                self.locked_files.add(f)

    def _unlock_files(self, filenames):
        with self.files_lock:
            for f in filenames:
                self.locked_files.discard(f)

    # ------------------------------------------------------------------
    # Audio Metadata (ffprobe)
    # ------------------------------------------------------------------
    def get_audio_metadata(self, file_path):
        """Extract audio duration and metadata using ffprobe."""
        if not self.ffprobe_bin or not os.path.isfile(file_path):
            stat = os.stat(file_path) if os.path.isfile(file_path) else None
            return {
                "duration": 0.0,
                "duration_formatted": "00:00",
                "bitrate": 0,
                "sample_rate": 0,
                "channels": 0,
                "format": os.path.splitext(file_path)[1].lstrip('.'),
                "size": stat.st_size if stat else 0
            }

        cmd = [
            self.ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            data = json.loads(res.stdout)
            format_info = data.get("format", {})
            duration = float(format_info.get("duration", 0.0))
            bitrate = int(format_info.get("bit_rate", 0))

            stream_info = {}
            for s in data.get("streams", []):
                if s.get("codec_type") == "audio":
                    stream_info = s
                    break

            sample_rate = int(stream_info.get("sample_rate", 0))
            channels = int(stream_info.get("channels", 0))

            mins = int(duration // 60)
            secs = int(duration % 60)
            dur_fmt = f"{mins:02d}:{secs:02d}"

            return {
                "duration": round(duration, 2),
                "duration_formatted": dur_fmt,
                "bitrate": bitrate,
                "sample_rate": sample_rate,
                "channels": channels,
                "format": format_info.get("format_name", "").split(",")[0],
                "size": int(format_info.get("size", os.path.getsize(file_path)))
            }
        except Exception as e:
            stat = os.stat(file_path) if os.path.isfile(file_path) else None
            return {
                "duration": 0.0,
                "duration_formatted": "00:00",
                "bitrate": 0,
                "sample_rate": 0,
                "channels": 0,
                "format": os.path.splitext(file_path)[1].lstrip('.'),
                "size": stat.st_size if stat else 0
            }

    # ------------------------------------------------------------------
    # Task Management
    # ------------------------------------------------------------------
    def get_task(self, task_id):
        with self.task_lock:
            return self.tasks.get(task_id)

    def _create_task(self, task_type, source_files, target_file, extra_info=None):
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "progress": 0.0,
            "source_files": source_files,
            "target_file": target_file,
            "source_size": 0,
            "output_size": 0,
            "reduction_percent": 0.0,
            "duration": 0.0,
            "error": None,
            "warning": None,
            "created_at": time.time(),
            "completed_at": None
        }
        if extra_info:
            task.update(extra_info)

        with self.task_lock:
            self.tasks[task_id] = task

        return task_id

    def _update_task(self, task_id, **kwargs):
        with self.task_lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(kwargs)

    # ------------------------------------------------------------------
    # Audio Conversion Worker
    # ------------------------------------------------------------------
    def submit_convert_task(self, source_filename, target_filename, options, overwrite=False):
        if not self.is_available():
            raise RuntimeError("FFmpeg is not installed or available on the server.")

        source_path = os.path.join(self.music_dir, source_filename)
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"Source file not found: {source_filename}")

        if self.is_file_locked(source_filename):
            raise RuntimeError(f"File '{source_filename}' is currently busy in another task.")

        in_ext = os.path.splitext(source_filename)[1].lower()
        out_ext = os.path.splitext(target_filename)[1].lower()

        warning = None
        if is_lossy_transcode(in_ext, out_ext):
            warning = "Transcoding between lossy formats may result in slight audio quality degradation."

        source_size = os.path.getsize(source_path)
        meta = self.get_audio_metadata(source_path)
        total_duration = meta.get("duration", 0.0)

        task_id = self._create_task(
            task_type="convert",
            source_files=[source_filename],
            target_file=target_filename,
            extra_info={
                "source_size": source_size,
                "duration": total_duration,
                "warning": warning,
                "overwrite": overwrite
            }
        )

        self._lock_files([source_filename, target_filename])
        self.executor.submit(self._run_convert_job, task_id, source_filename, target_filename, options, overwrite, total_duration)
        return task_id

    def _run_convert_job(self, task_id, source_filename, target_filename, options, overwrite, total_duration):
        source_path = os.path.join(self.music_dir, source_filename)
        target_path = os.path.join(self.music_dir, target_filename)
        temp_target_path = os.path.join(self.music_dir, f".tmp_conv_{task_id}_{target_filename}")

        self._update_task(task_id, status="processing", progress=5.0)
        if self.db_service:
            self.db_service.log_event("audio_convert_started", "server", filename=source_filename, status="info")

        try:
            cmd = build_convert_command(self.ffmpeg_bin, source_path, temp_target_path, options)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Read progress from stdout
            for line in proc.stdout:
                line = line.strip()
                if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                    try:
                        val = int(line.split("=")[1])
                        current_sec = val / 1_000_000.0 if "us=" in line else val / 1000.0
                        if total_duration > 0:
                            pct = min(98.0, max(5.0, (current_sec / total_duration) * 100.0))
                            self._update_task(task_id, progress=round(pct, 1))
                    except (ValueError, IndexError):
                        pass

            ret_code = proc.wait()
            if ret_code != 0:
                err = proc.stderr.read()
                raise RuntimeError(f"FFmpeg conversion failed (code {ret_code}): {err[:300]}")

            if not os.path.isfile(temp_target_path) or os.path.getsize(temp_target_path) == 0:
                raise RuntimeError("Output file was not created or is 0 bytes.")

            out_size = os.path.getsize(temp_target_path)
            src_size = os.path.getsize(source_path)
            reduction = round((1.0 - (out_size / src_size)) * 100.0, 1) if src_size > 0 else 0.0

            # Atomic replace or save
            if overwrite and source_path == target_path:
                os.replace(temp_target_path, target_path)
            else:
                os.replace(temp_target_path, target_path)

            self._update_task(
                task_id,
                status="completed",
                progress=100.0,
                output_size=out_size,
                reduction_percent=reduction,
                completed_at=time.time()
            )
            if self.db_service:
                self.db_service.log_event("audio_convert_completed", "server", filename=target_filename, file_size=out_size, status="success")

        except Exception as e:
            if os.path.isfile(temp_target_path):
                try:
                    os.remove(temp_target_path)
                except Exception:
                    pass
            self._update_task(
                task_id,
                status="failed",
                error=str(e),
                completed_at=time.time()
            )
            if self.db_service:
                self.db_service.log_event("audio_convert_failed", "server", filename=source_filename, status="failed", error_details=str(e)[:200])
        finally:
            self._unlock_files([source_filename, target_filename])

    # ------------------------------------------------------------------
    # Audio Merge Worker
    # ------------------------------------------------------------------
    def submit_merge_task(self, source_filenames, target_filename, options):
        if not self.is_available():
            raise RuntimeError("FFmpeg is not installed or available on the server.")

        if len(source_filenames) < 2:
            raise ValueError("Select at least 2 tracks to merge.")

        for f in source_filenames:
            sp = os.path.join(self.music_dir, f)
            if not os.path.isfile(sp):
                raise FileNotFoundError(f"Track not found: {f}")
            if self.is_file_locked(f):
                raise RuntimeError(f"Track '{f}' is currently busy in another task.")

        input_paths = [os.path.join(self.music_dir, f) for f in source_filenames]
        total_source_size = sum(os.path.getsize(p) for p in input_paths)

        # Collect track durations
        track_durations = []
        for p in input_paths:
            m = self.get_audio_metadata(p)
            track_durations.append(m.get("duration", 0.0))

        crossfade = float(options.get("crossfade", 0.0))
        silence = float(options.get("silence", 0.0))

        # Calculate estimated total duration
        if crossfade > 0:
            est_total_duration = sum(track_durations) - (crossfade * (len(track_durations) - 1))
        else:
            est_total_duration = sum(track_durations) + (silence * (len(track_durations) - 1))

        task_id = self._create_task(
            task_type="merge",
            source_files=source_filenames,
            target_file=target_filename,
            extra_info={
                "source_size": total_source_size,
                "duration": round(est_total_duration, 2),
                "track_count": len(source_filenames)
            }
        )

        all_locked = list(source_filenames) + [target_filename]
        self._lock_files(all_locked)
        self.executor.submit(
            self._run_merge_job,
            task_id,
            input_paths,
            target_filename,
            options,
            track_durations,
            est_total_duration,
            all_locked
        )
        return task_id

    def _run_merge_job(self, task_id, input_paths, target_filename, options, track_durations, est_total_duration, all_locked):
        target_path = os.path.join(self.music_dir, target_filename)
        temp_target_path = os.path.join(self.music_dir, f".tmp_merge_{task_id}_{target_filename}")

        self._update_task(task_id, status="processing", progress=5.0)
        if self.db_service:
            self.db_service.log_event("audio_merge_started", "server", filename=target_filename, status="info")

        try:
            cmd = build_merge_command(self.ffmpeg_bin, input_paths, temp_target_path, options, track_durations)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            for line in proc.stdout:
                line = line.strip()
                if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                    try:
                        val = int(line.split("=")[1])
                        current_sec = val / 1_000_000.0 if "us=" in line else val / 1000.0
                        if est_total_duration > 0:
                            pct = min(98.0, max(5.0, (current_sec / est_total_duration) * 100.0))
                            self._update_task(task_id, progress=round(pct, 1))
                    except (ValueError, IndexError):
                        pass

            ret_code = proc.wait()
            if ret_code != 0:
                err = proc.stderr.read()
                raise RuntimeError(f"FFmpeg merge failed (code {ret_code}): {err[:300]}")

            if not os.path.isfile(temp_target_path) or os.path.getsize(temp_target_path) == 0:
                raise RuntimeError("Merged output file was not created or is 0 bytes.")

            out_size = os.path.getsize(temp_target_path)
            meta = self.get_audio_metadata(temp_target_path)

            os.replace(temp_target_path, target_path)

            self._update_task(
                task_id,
                status="completed",
                progress=100.0,
                output_size=out_size,
                duration=meta.get("duration", est_total_duration),
                completed_at=time.time()
            )
            if self.db_service:
                self.db_service.log_event("audio_merge_completed", "server", filename=target_filename, file_size=out_size, status="success")

        except Exception as e:
            if os.path.isfile(temp_target_path):
                try:
                    os.remove(temp_target_path)
                except Exception:
                    pass
            self._update_task(
                task_id,
                status="failed",
                error=str(e),
                completed_at=time.time()
            )
            if self.db_service:
                self.db_service.log_event("audio_merge_failed", "server", filename=target_filename, status="failed", error_details=str(e)[:200])
        finally:
            self._unlock_files(all_locked)

