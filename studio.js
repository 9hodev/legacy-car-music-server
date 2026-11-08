/**
 * Audio Merge Studio Client JavaScript
 * Drag-and-drop ordering, queue management, and real-time FFmpeg progress tracking
 */

var studioFiles = [];
var mergeQueue = [];
var mergeTaskId = null;
var mergePollTimer = null;
var draggedItemIndex = null;

// DOM Elements
var availableTracksList = document.getElementById("available-tracks-list");
var availCount = document.getElementById("avail-count");
var queueContainer = document.getElementById("queue-container");
var queueCount = document.getElementById("queue-count");
var queueTotalSize = document.getElementById("queue-total-size");
var queueTotalDuration = document.getElementById("queue-total-duration");

var mergeFilename = document.getElementById("merge-filename");
var mergeFormat = document.getElementById("merge-format");
var mergeBitrate = document.getElementById("merge-bitrate");
var mergeBitrateGroup = document.getElementById("merge-bitrate-group");
var mergeSamplerate = document.getElementById("merge-samplerate");
var mergeChannels = document.getElementById("merge-channels");
var mergeCrossfade = document.getElementById("merge-crossfade");
var mergeSilence = document.getElementById("merge-silence");
var silenceGroup = document.getElementById("silence-group");
var btnMergeStart = document.getElementById("btn-merge-start");

var mergeProgressBox = document.getElementById("merge-progress-box");
var mergeStatusText = document.getElementById("merge-status-text");
var mergePercentage = document.getElementById("merge-percentage");
var mergeProgressBar = document.getElementById("merge-progress-bar");
var mergeProgressDetails = document.getElementById("merge-progress-details");
var mergeSuccessActions = document.getElementById("merge-success-actions");
var btnDownloadMerged = document.getElementById("btn-download-merged");
var toast = document.getElementById("toast");

document.addEventListener("DOMContentLoaded", function () {
  loadStudioFiles();
});

// ----------------------------------------------------------------------
// Load & Render Available Library Tracks
// ----------------------------------------------------------------------
function loadStudioFiles() {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/api/files?meta=1", true);
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var data = JSON.parse(xhr.responseText);
        studioFiles = data.files || [];
        renderAvailableTracks(studioFiles);
        if (availCount) {
          availCount.textContent = studioFiles.length + (studioFiles.length === 1 ? " file" : " files");
        }
      } catch (e) {
        if (availableTracksList) {
          availableTracksList.innerHTML = '<div class="table-empty" style="color:#ff7b72;">Failed to parse library tracks.</div>';
        }
      }
    } else {
      if (availableTracksList) {
        availableTracksList.innerHTML = '<div class="table-empty" style="color:#ff7b72;">Error fetching files.</div>';
      }
    }
  };
  xhr.onerror = function () {
    if (availableTracksList) {
      availableTracksList.innerHTML = '<div class="table-empty" style="color:#ff7b72;">Connection error.</div>';
    }
  };
  xhr.send();
}

function renderAvailableTracks(files) {
  if (!availableTracksList) return;

  if (files.length === 0) {
    availableTracksList.innerHTML = '<div class="table-empty">No music tracks found on server.<br><a href="/admin" class="btn btn-primary btn-small" style="margin-top:10px;">Upload Files</a></div>';
    return;
  }

  var html = "";
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var safeName = escapeHtml(f.name);
    var ext = (f.name.split('.').pop() || "audio").toUpperCase();
    var durStr = f.duration_formatted ? f.duration_formatted : "--:--";
    var sizeStr = f.size_formatted || formatBytes(f.size);

    html += '<div class="studio-track-item">' +
      '<div class="track-left">' +
        '<span class="badge-format">' + ext + '</span>' +
        '<div class="track-meta">' +
          '<div class="track-title" title="' + safeName + '">' + safeName + '</div>' +
          '<div class="track-sub">' + durStr + ' &bull; ' + sizeStr + '</div>' +
        '</div>' +
      '</div>' +
      '<button class="btn btn-secondary btn-small" onclick="addToQueueByIndex(' + i + ')">' +
        '+ Add' +
      '</button>' +
    '</div>';
  }

  availableTracksList.innerHTML = html;
}

// ----------------------------------------------------------------------
// Queue Management (Drag & Drop Reordering, Up/Down, Remove)
// ----------------------------------------------------------------------
function addToQueueByIndex(idx) {
  if (idx < 0 || idx >= studioFiles.length) return;
  var track = studioFiles[idx];
  mergeQueue.push({
    name: track.name,
    size: track.size || 0,
    size_formatted: track.size_formatted || formatBytes(track.size),
    duration: track.duration || 0,
    duration_formatted: track.duration_formatted || "00:00"
  });

  renderQueue();
  showToast("Added to queue: " + track.name);
}

function removeFromQueue(queueIdx) {
  if (queueIdx >= 0 && queueIdx < mergeQueue.length) {
    var removed = mergeQueue.splice(queueIdx, 1);
    renderQueue();
    if (removed.length > 0) {
      showToast("Removed: " + removed[0].name);
    }
  }
}

function moveQueueItem(fromIdx, toIdx) {
  if (toIdx < 0 || toIdx >= mergeQueue.length || fromIdx === toIdx) return;
  var item = mergeQueue.splice(fromIdx, 1)[0];
  mergeQueue.splice(toIdx, 0, item);
  renderQueue();
}

function clearQueue() {
  if (mergeQueue.length === 0) return;
  if (confirm("Clear all tracks from the merge queue?")) {
    mergeQueue = [];
    renderQueue();
    showToast("Queue cleared");
  }
}

function renderQueue() {
  if (!queueContainer) return;

  if (queueCount) {
    queueCount.textContent = mergeQueue.length + (mergeQueue.length === 1 ? " track" : " tracks");
  }

  if (mergeQueue.length === 0) {
    queueContainer.innerHTML = '<div class="queue-empty">' +
      '<div class="queue-empty-icon">&#127926;</div>' +
      '<p><strong>Your merge queue is empty</strong></p>' +
      '<span>Add 2 or more tracks from the left list to begin merging</span>' +
    '</div>';
    updateQueueStats();
    return;
  }

  var html = "";
  for (var i = 0; i < mergeQueue.length; i++) {
    var item = mergeQueue[i];
    var safeName = escapeHtml(item.name);
    var ext = (item.name.split('.').pop() || "audio").toUpperCase();
    var durStr = item.duration_formatted || "--:--";
    var sizeStr = item.size_formatted || formatBytes(item.size);

    var canMoveUp = i > 0;
    var canMoveDown = i < mergeQueue.length - 1;

    html += '<div class="queue-item" draggable="true" data-index="' + i + '">' +
      '<div class="queue-order-badge">' + (i + 1) + '</div>' +
      '<div class="queue-drag-handle" title="Drag to reorder">&#8801;</div>' +
      '<div class="queue-track-info">' +
        '<span class="badge-format">' + ext + '</span>' +
        '<div class="queue-track-text">' +
          '<strong class="queue-title" title="' + safeName + '">' + safeName + '</strong>' +
          '<span class="queue-sub">' + durStr + ' &bull; ' + sizeStr + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="queue-item-actions">' +
        '<button class="btn btn-secondary btn-icon" onclick="moveQueueItem(' + i + ', ' + (i - 1) + ')" ' + (canMoveUp ? '' : 'disabled') + ' title="Move Up">&#9650;</button>' +
        '<button class="btn btn-secondary btn-icon" onclick="moveQueueItem(' + i + ', ' + (i + 1) + ')" ' + (canMoveDown ? '' : 'disabled') + ' title="Move Down">&#9660;</button>' +
        '<button class="btn btn-danger btn-icon" onclick="removeFromQueue(' + i + ')" title="Remove Track">&times;</button>' +
      '</div>' +
    '</div>';
  }

  queueContainer.innerHTML = html;
  attachDragAndDropToQueue();
  updateQueueStats();
}

function updateQueueStats() {
  var totalBytes = 0;
  var totalSecs = 0;
  for (var i = 0; i < mergeQueue.length; i++) {
    totalBytes += (mergeQueue[i].size || 0);
    totalSecs += (mergeQueue[i].duration || 0);
  }

  if (queueTotalSize) {
    queueTotalSize.textContent = formatBytes(totalBytes);
  }

  var crossfade = parseFloat(mergeCrossfade.value) || 0;
  var silence = parseFloat(mergeSilence.value) || 0;

  var estSecs = totalSecs;
  if (mergeQueue.length > 1) {
    if (crossfade > 0) {
      estSecs = Math.max(0, totalSecs - (crossfade * (mergeQueue.length - 1)));
    } else if (silence > 0) {
      estSecs = totalSecs + (silence * (mergeQueue.length - 1));
    }
  }

  var mins = Math.floor(estSecs / 60);
  var secs = Math.floor(estSecs % 60);
  var durStr = (mins < 10 ? "0" : "") + mins + ":" + (secs < 10 ? "0" : "") + secs;

  if (queueTotalDuration) {
    queueTotalDuration.textContent = durStr;
  }
}

// ----------------------------------------------------------------------
// Drag & Drop HTML5 Reordering
// ----------------------------------------------------------------------
function attachDragAndDropToQueue() {
  var items = queueContainer.querySelectorAll(".queue-item");
  items.forEach(function (el) {
    el.addEventListener("dragstart", function (e) {
      draggedItemIndex = parseInt(el.getAttribute("data-index"));
      el.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
    });

    el.addEventListener("dragend", function () {
      el.classList.remove("dragging");
      draggedItemIndex = null;
    });

    el.addEventListener("dragover", function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      el.classList.add("drag-target");
    });

    el.addEventListener("dragleave", function () {
      el.classList.remove("drag-target");
    });

    el.addEventListener("drop", function (e) {
      e.preventDefault();
      el.classList.remove("drag-target");
      var targetIdx = parseInt(el.getAttribute("data-index"));
      if (draggedItemIndex !== null && draggedItemIndex !== targetIdx) {
        moveQueueItem(draggedItemIndex, targetIdx);
      }
    });
  });
}

// ----------------------------------------------------------------------
// Settings Handlers
// ----------------------------------------------------------------------
function toggleMergeBitrate() {
  var fmt = mergeFormat.value.toLowerCase();
  if (mergeBitrateGroup) {
    mergeBitrateGroup.style.display = (fmt === "wav" || fmt === "flac") ? "none" : "block";
  }
}

function onCrossfadeChange() {
  var cf = parseFloat(mergeCrossfade.value) || 0;
  if (cf > 0) {
    if (mergeSilence) mergeSilence.value = "0";
    if (silenceGroup) silenceGroup.style.display = "none";
  } else {
    if (silenceGroup) silenceGroup.style.display = "block";
  }
  updateQueueStats();
}

// ----------------------------------------------------------------------
// Submit Merge
// ----------------------------------------------------------------------
function submitMerge() {
  if (mergeQueue.length < 2) {
    alert("Please add at least 2 tracks to the merge queue.");
    return;
  }

  var sourceFiles = mergeQueue.map(function (item) { return item.name; });
  var outFmt = mergeFormat.value;
  var customName = mergeFilename.value.trim();
  var bitrate = mergeBitrate.value;
  var sampleRate = parseInt(mergeSamplerate.value) || 44100;
  var channels = parseInt(mergeChannels.value) || 2;
  var crossfade = parseFloat(mergeCrossfade.value) || 0.0;
  var silence = parseFloat(mergeSilence.value) || 0.0;

  btnMergeStart.disabled = true;
  mergeProgressBox.style.display = "block";
  mergeSuccessActions.style.display = "none";
  mergeProgressBar.style.width = "5%";
  mergePercentage.textContent = "5%";
  mergeStatusText.textContent = "Starting FFmpeg merge process...";
  mergeProgressDetails.textContent = "Decoding, resampling and aligning audio streams...";

  var payload = {
    source_filenames: sourceFiles,
    output_format: outFmt,
    target_filename: customName,
    bitrate: bitrate,
    sample_rate: sampleRate,
    channels: channels,
    crossfade: crossfade,
    silence: silence
  };

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/merge", true);
  xhr.setRequestHeader("Content-Type", "application/json; charset=utf-8");

  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success && resp.task_id) {
          mergeTaskId = resp.task_id;
          pollMergeProgress(resp.task_id);
        } else {
          mergeStatusText.textContent = "Merge failed: " + (resp.error || "Unknown error");
          btnMergeStart.disabled = false;
        }
      } catch (e) {
        mergeStatusText.textContent = "Error parsing server response.";
        btnMergeStart.disabled = false;
      }
    } else {
      var errMsg = "Merge request failed (Status " + xhr.status + ")";
      try {
        var errResp = JSON.parse(xhr.responseText);
        if (errResp.error) errMsg = errResp.error;
      } catch (e) {}
      mergeStatusText.textContent = errMsg;
      btnMergeStart.disabled = false;
    }
  };

  xhr.onerror = function () {
    mergeStatusText.textContent = "Network error during merge request.";
    btnMergeStart.disabled = false;
  };

  xhr.send(JSON.stringify(payload));
}

function pollMergeProgress(taskId) {
  if (mergePollTimer) clearInterval(mergePollTimer);

  mergePollTimer = setInterval(function () {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/tasks/" + taskId, true);
    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var resp = JSON.parse(xhr.responseText);
          if (resp.success && resp.task) {
            updateMergeUI(resp.task);
          }
        } catch (e) {}
      }
    };
    xhr.send();
  }, 500);
}

function updateMergeUI(task) {
  var pct = Math.round(task.progress || 0);
  mergeProgressBar.style.width = pct + "%";
  mergePercentage.textContent = pct + "%";

  if (task.status === "processing") {
    mergeStatusText.textContent = "Encoding with FFmpeg: " + task.target_file;
    mergeProgressDetails.textContent = "Merging " + (task.source_files ? task.source_files.length : "") + " tracks in background (" + pct + "%)";
  } else if (task.status === "completed") {
    clearInterval(mergePollTimer);
    mergePollTimer = null;
    mergeTaskId = null;
    btnMergeStart.disabled = false;

    var outSizeStr = formatBytes(task.output_size);
    var srcSizeStr = formatBytes(task.source_size);

    var mins = Math.floor((task.duration || 0) / 60);
    var secs = Math.floor((task.duration || 0) % 60);
    var durFormatted = (mins < 10 ? "0" : "") + mins + ":" + (secs < 10 ? "0" : "") + secs;

    mergeStatusText.innerHTML = "<strong style='color:#00e676;'>&#10004; Merge Completed Successfully!</strong>";
    mergeProgressDetails.textContent = "Output: " + task.target_file + " (" + outSizeStr + ") &bull; Total Duration: " + durFormatted + " &bull; Sources: " + srcSizeStr;

    if (btnDownloadMerged) {
      btnDownloadMerged.href = "/download/" + encodeURIComponent(task.target_file);
      btnDownloadMerged.setAttribute("download", task.target_file);
    }
    mergeSuccessActions.style.display = "flex";

    showToast("Merge complete: " + task.target_file);
    loadStudioFiles();
  } else if (task.status === "failed") {
    clearInterval(mergePollTimer);
    mergePollTimer = null;
    mergeTaskId = null;
    btnMergeStart.disabled = false;

    mergeStatusText.innerHTML = "<strong style='color:#ff7b72;'>&#10008; Merge Failed</strong>";
    mergeProgressDetails.textContent = task.error || "Unknown FFmpeg error occurred during merge.";
  }
}

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------
function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(function () {
    toast.classList.remove("show");
  }, 2800);
}

function formatBytes(bytes) {
  if (bytes === 0 || !bytes) return "0 B";
  var k = 1024;
  var sizes = ["B", "KB", "MB", "GB", "TB"];
  var i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function escapeHtml(text) {
  var div = document.createElement("div");
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}
