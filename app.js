/**
 * Local Music Drop Server - Admin Application JavaScript
 * Zero dependencies, Vanilla JS using XMLHttpRequest for progress tracking
 */

var filesList = [];
var isUploading = false;
var currentRenameFile = "";
var currentOptimizeFile = "";
var activeTaskId = null;
var taskPollTimer = null;

// DOM Elements
var dropZone = document.getElementById("drop-zone");
var fileInput = document.getElementById("file-input");
var progressContainer = document.getElementById("upload-progress-container");
var progressBar = document.getElementById("upload-progress-bar");
var progressText = document.getElementById("upload-status-text");
var progressPercent = document.getElementById("upload-percentage");
var progressDetails = document.getElementById("upload-details");
var alertBox = document.getElementById("alert-box");
var filesTbody = document.getElementById("files-tbody");
var libraryCount = document.getElementById("library-count");
var libraryTotalSize = document.getElementById("library-total-size");
var toast = document.getElementById("toast");

// Modals
var renameModal = document.getElementById("rename-modal");
var renameInput = document.getElementById("rename-input");
var renameOriginalName = document.getElementById("rename-original-name");
var renameExtAddon = document.getElementById("rename-ext-addon");

var optimizeModal = document.getElementById("optimize-modal");
var optSourceName = document.getElementById("opt-source-name");
var optSourceInfo = document.getElementById("opt-source-info");
var optFormat = document.getElementById("opt-format");
var optBitrate = document.getElementById("opt-bitrate");
var optBitrateGroup = document.getElementById("opt-bitrate-group");
var optSamplerate = document.getElementById("opt-samplerate");
var optChannels = document.getElementById("opt-channels");
var optOutputFilename = document.getElementById("opt-output-filename");
var optOverwrite = document.getElementById("opt-overwrite");
var optLossyWarning = document.getElementById("opt-lossy-warning");
var optProgressBox = document.getElementById("opt-progress-box");
var optStatusText = document.getElementById("opt-status-text");
var optPercentage = document.getElementById("opt-percentage");
var optProgressBar = document.getElementById("opt-progress-bar");
var optProgressDetails = document.getElementById("opt-progress-details");
var optBtnCancel = document.getElementById("opt-btn-cancel");
var optBtnSubmit = document.getElementById("opt-btn-submit");

// Initialize Event Listeners
document.addEventListener("DOMContentLoaded", function () {
  initDragAndDrop();
  initFileInput();
  loadFilesList();
});

// ----------------------------------------------------------------------
// Drag and Drop Handling
// ----------------------------------------------------------------------
function initDragAndDrop() {
  if (!dropZone) return;

  ["dragenter", "dragover"].forEach(function (eventName) {
    dropZone.addEventListener(eventName, function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("dragover");
    }, false);
  });

  ["dragleave", "drop"].forEach(function (eventName) {
    dropZone.addEventListener(eventName, function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("dragover");
    }, false);
  });

  dropZone.addEventListener("drop", function (e) {
    var dt = e.dataTransfer;
    var files = dt.files;
    if (files && files.length > 0) {
      handleFilesUpload(files);
    }
  }, false);

  dropZone.addEventListener("click", function (e) {
    if (e.target.tagName !== "BUTTON" && fileInput) {
      fileInput.click();
    }
  });
}

function initFileInput() {
  if (!fileInput) return;
  fileInput.addEventListener("change", function () {
    if (this.files && this.files.length > 0) {
      handleFilesUpload(this.files);
    }
  });
}

// ----------------------------------------------------------------------
// Upload Processing with XMLHttpRequest
// ----------------------------------------------------------------------
function handleFilesUpload(files) {
  if (isUploading) {
    showAlert("An upload is already in progress. Please wait.", "error");
    return;
  }

  var validFiles = [];
  var allowedExts = [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"];

  for (var i = 0; i < files.length; i++) {
    var file = files[i];
    var nameLower = file.name.toLowerCase();
    var hasValidExt = allowedExts.some(function (ext) {
      return nameLower.endsWith(ext);
    });

    if (hasValidExt) {
      validFiles.push(file);
    } else {
      showAlert("Skipped '" + file.name + "': Only audio files are supported.", "error");
    }
  }

  if (validFiles.length === 0) return;
  uploadQueue(validFiles, 0);
}

function uploadQueue(files, index) {
  if (index >= files.length) {
    isUploading = false;
    if (fileInput) fileInput.value = "";
    loadFilesList();
    showAlert("All files processed successfully!", "success");
    return;
  }

  isUploading = true;
  var file = files[index];
  var currentNum = index + 1;
  var totalNum = files.length;

  var formData = new FormData();
  formData.append("file", file, file.name);

  var xhr = new XMLHttpRequest();
  var startTime = Date.now();

  progressContainer.style.display = "block";
  progressText.textContent = "Uploading (" + currentNum + "/" + totalNum + "): " + file.name;
  progressBar.style.width = "0%";
  progressPercent.textContent = "0%";
  progressDetails.textContent = "Starting upload...";

  xhr.upload.onprogress = function (e) {
    if (e.lengthComputable) {
      var percentComplete = Math.round((e.loaded / e.total) * 100);
      progressBar.style.width = percentComplete + "%";
      progressPercent.textContent = percentComplete + "%";

      var loadedFormatted = formatBytes(e.loaded);
      var totalFormatted = formatBytes(e.total);
      
      var elapsedSec = (Date.now() - startTime) / 1000;
      var speedFormatted = "";
      if (elapsedSec > 0.5) {
        var bytesPerSec = e.loaded / elapsedSec;
        speedFormatted = " • " + formatBytes(bytesPerSec) + "/s";
      }

      progressDetails.textContent = loadedFormatted + " of " + totalFormatted + speedFormatted;
    }
  };

  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success) {
          showToast("Uploaded: " + file.name);
          uploadQueue(files, index + 1);
        } else {
          showAlert("Upload failed: " + (resp.error || "Unknown server error"), "error");
          isUploading = false;
        }
      } catch (err) {
        showAlert("Failed to parse server response", "error");
        isUploading = false;
      }
    } else {
      var errMsg = "Upload error (Status " + xhr.status + ")";
      try {
        var errResp = JSON.parse(xhr.responseText);
        if (errResp.error) errMsg = errResp.error;
      } catch (e) {}
      showAlert(errMsg, "error");
      isUploading = false;
    }
  };

  xhr.onerror = function () {
    showAlert("Network connection error during upload. Please check Wi-Fi connection.", "error");
    isUploading = false;
  };

  xhr.open("POST", "/api/upload", true);
  xhr.send(formData);
}

// ----------------------------------------------------------------------
// Load & Render Music Library
// ----------------------------------------------------------------------
function loadFilesList() {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/api/files?meta=1", true);
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var data = JSON.parse(xhr.responseText);
        filesList = data.files || [];
        renderMusicTable(filesList);
        updateLibraryStats(filesList);
      } catch (e) {
        renderTableError("Failed to parse music library data");
      }
    } else {
      renderTableError("Failed to fetch music files list from server");
    }
  };
  xhr.onerror = function () {
    renderTableError("Connection error while connecting to server");
  };
  xhr.send();
}

function updateLibraryStats(list) {
  if (libraryCount) {
    libraryCount.textContent = list.length + (list.length === 1 ? " song" : " songs");
  }

  var totalBytes = 0;
  for (var i = 0; i < list.length; i++) {
    totalBytes += (list[i].size || 0);
  }

  if (libraryTotalSize) {
    libraryTotalSize.textContent = formatBytes(totalBytes);
  }
}

function renderMusicTable(list) {
  if (!filesTbody) return;

  if (list.length === 0) {
    filesTbody.innerHTML = '<tr><td colspan="3" class="table-empty">No music files uploaded yet. Drag & drop files above to start!</td></tr>';
    return;
  }

  var rowsHtml = "";
  for (var i = 0; i < list.length; i++) {
    var file = list[i];
    var safeName = escapeHtml(file.name);
    var fullUrl = window.location.origin + file.url;
    var isLocked = Boolean(file.is_locked);
    var durationStr = file.duration_formatted ? ' <span class="badge-dim">' + file.duration_formatted + '</span>' : '';

    var lockedBadge = isLocked ? ' <span class="badge badge-warning">Processing</span>' : '';

    rowsHtml += '<tr>' +
      '<td>' +
        '<div class="song-cell-title">' +
          '<span class="song-icon">&#9835;</span>' +
          '<span>' + safeName + '</span>' +
          durationStr +
          lockedBadge +
        '</div>' +
      '</td>' +
      '<td>' + (file.size_formatted || formatBytes(file.size)) + '</td>' +
      '<td>' +
        '<div class="table-actions">' +
          '<button class="btn btn-secondary btn-small" onclick="copyDownloadUrl(\'' + escapeJsString(fullUrl) + '\')">' +
            '&#128203; Copy' +
          '</button>' +
          '<button class="btn btn-studio btn-small" onclick="openOptimizeModal(\'' + escapeJsString(file.name) + '\', ' + (file.size || 0) + ')" ' + (isLocked ? 'disabled' : '') + '>' +
            '&#9881; Optimize' +
          '</button>' +
          '<button class="btn btn-secondary btn-small" onclick="openRenameModal(\'' + escapeJsString(file.name) + '\')" ' + (isLocked ? 'disabled' : '') + '>' +
            '&#9998; Rename' +
          '</button>' +
          '<a class="btn btn-primary btn-small" href="' + file.url + '" download>' +
            '&#11015; DL' +
          '</a>' +
          '<button class="btn btn-danger btn-small" onclick="deleteFile(\'' + escapeJsString(file.name) + '\')" ' + (isLocked ? 'disabled' : '') + '>' +
            '&#128465; Delete' +
          '</button>' +
        '</div>' +
      '</td>' +
    '</tr>';
  }

  filesTbody.innerHTML = rowsHtml;
}

function renderTableError(msg) {
  if (filesTbody) {
    filesTbody.innerHTML = '<tr><td colspan="3" class="table-empty" style="color: #ff7b72;">' + escapeHtml(msg) + '</td></tr>';
  }
}

// ----------------------------------------------------------------------
// Rename File Feature
// ----------------------------------------------------------------------
function openRenameModal(filename) {
  currentRenameFile = filename;
  var dotIdx = filename.lastIndexOf(".");
  var base = dotIdx !== -1 ? filename.substring(0, dotIdx) : filename;
  var ext = dotIdx !== -1 ? filename.substring(dotIdx) : "";

  renameOriginalName.textContent = filename;
  renameInput.value = base;
  renameExtAddon.textContent = ext;
  renameModal.style.display = "flex";
  renameInput.focus();
}

function closeRenameModal() {
  renameModal.style.display = "none";
  currentRenameFile = "";
}

function submitRename() {
  var newBase = renameInput.value.trim();
  if (!newBase) {
    alert("Please enter a valid filename.");
    return;
  }

  var dotIdx = currentRenameFile.lastIndexOf(".");
  var ext = dotIdx !== -1 ? currentRenameFile.substring(dotIdx) : "";
  var finalNewName = newBase + ext;

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/rename", true);
  xhr.setRequestHeader("Content-Type", "application/json; charset=utf-8");

  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success) {
          showToast("Renamed to: " + resp.new_name);
          closeRenameModal();
          loadFilesList();
        } else {
          alert("Rename error: " + (resp.error || "Unknown error"));
        }
      } catch (e) {
        alert("Failed to parse rename response.");
      }
    } else {
      var errMsg = "Rename failed with status " + xhr.status;
      try {
        var errResp = JSON.parse(xhr.responseText);
        if (errResp.error) errMsg = errResp.error;
      } catch (e) {}
      alert(errMsg);
    }
  };

  xhr.onerror = function () {
    alert("Network error during rename.");
  };

  xhr.send(JSON.stringify({
    old_name: currentRenameFile,
    new_name: finalNewName
  }));
}

// ----------------------------------------------------------------------
// Audio Optimize / Convert Feature
// ----------------------------------------------------------------------
function openOptimizeModal(filename, size) {
  currentOptimizeFile = filename;
  optSourceName.textContent = filename;
  optSourceInfo.textContent = "File size: " + formatBytes(size);

  var dotIdx = filename.lastIndexOf(".");
  var base = dotIdx !== -1 ? filename.substring(0, dotIdx) : filename;
  optOutputFilename.placeholder = base + "_opt.mp3";
  optOutputFilename.value = "";
  optOverwrite.checked = false;

  optProgressBox.style.display = "none";
  optProgressBar.style.width = "0%";
  optPercentage.textContent = "0%";
  optBtnSubmit.disabled = false;
  optBtnCancel.disabled = false;

  checkLossyWarning();
  optimizeModal.style.display = "flex";
}

function closeOptimizeModal() {
  if (activeTaskId && taskPollTimer) {
    clearInterval(taskPollTimer);
    taskPollTimer = null;
    activeTaskId = null;
  }
  optimizeModal.style.display = "none";
  currentOptimizeFile = "";
}

function checkLossyWarning() {
  var inExt = "";
  var dotIdx = currentOptimizeFile.lastIndexOf(".");
  if (dotIdx !== -1) inExt = currentOptimizeFile.substring(dotIdx).toLowerCase();

  var outFmt = optFormat.value.toLowerCase();
  var lossyFormats = ["mp3", "m4a", "aac", "ogg", "opus"];
  var inIsLossy = lossyFormats.some(function (f) { return inExt === "." + f; });
  var outIsLossy = lossyFormats.indexOf(outFmt) !== -1;

  if (optBitrateGroup) {
    optBitrateGroup.style.display = (outFmt === "wav" || outFmt === "flac") ? "none" : "block";
  }

  if (inIsLossy && outIsLossy) {
    optLossyWarning.style.display = "block";
  } else {
    optLossyWarning.style.display = "none";
  }
}

function submitOptimize() {
  var outFmt = optFormat.value;
  var bitrate = optBitrate.value;
  var sampleRate = optSamplerate.value ? parseInt(optSamplerate.value) : null;
  var channels = optChannels.value ? parseInt(optChannels.value) : null;
  var customName = optOutputFilename.value.trim();
  var overwrite = optOverwrite.checked;

  optBtnSubmit.disabled = true;
  optProgressBox.style.display = "block";
  optProgressBar.style.width = "5%";
  optPercentage.textContent = "5%";
  optStatusText.textContent = "Submitting conversion task to FFmpeg...";
  optProgressDetails.textContent = "Preparing background worker...";

  var payload = {
    source_filename: currentOptimizeFile,
    output_format: outFmt,
    bitrate: bitrate,
    sample_rate: sampleRate,
    channels: channels,
    target_filename: customName,
    overwrite: overwrite
  };

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/convert", true);
  xhr.setRequestHeader("Content-Type", "application/json; charset=utf-8");

  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success && resp.task_id) {
          activeTaskId = resp.task_id;
          pollTaskStatus(resp.task_id);
        } else {
          optStatusText.textContent = "Conversion failed: " + (resp.error || "Unknown error");
          optBtnSubmit.disabled = false;
        }
      } catch (e) {
        optStatusText.textContent = "Failed to parse conversion response.";
        optBtnSubmit.disabled = false;
      }
    } else {
      var errMsg = "Conversion error (Status " + xhr.status + ")";
      try {
        var errResp = JSON.parse(xhr.responseText);
        if (errResp.error) errMsg = errResp.error;
      } catch (e) {}
      optStatusText.textContent = errMsg;
      optBtnSubmit.disabled = false;
    }
  };

  xhr.onerror = function () {
    optStatusText.textContent = "Network error while connecting to server.";
    optBtnSubmit.disabled = false;
  };

  xhr.send(JSON.stringify(payload));
}

function pollTaskStatus(taskId) {
  if (taskPollTimer) clearInterval(taskPollTimer);

  taskPollTimer = setInterval(function () {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/tasks/" + taskId, true);
    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var resp = JSON.parse(xhr.responseText);
          if (resp.success && resp.task) {
            updateOptimizeProgress(resp.task);
          }
        } catch (e) {}
      }
    };
    xhr.send();
  }, 500);
}

function updateOptimizeProgress(task) {
  var pct = Math.round(task.progress || 0);
  optProgressBar.style.width = pct + "%";
  optPercentage.textContent = pct + "%";

  if (task.status === "processing") {
    optStatusText.textContent = "Encoding with FFmpeg: " + task.target_file;
    optProgressDetails.textContent = "Progress: " + pct + "% (Non-blocking background job)";
  } else if (task.status === "completed") {
    clearInterval(taskPollTimer);
    taskPollTimer = null;
    activeTaskId = null;

    var srcSizeStr = formatBytes(task.source_size);
    var outSizeStr = formatBytes(task.output_size);
    var redStr = task.reduction_percent > 0 ? " (" + task.reduction_percent + "% smaller)" : "";

    optStatusText.innerHTML = "<strong style='color:#00e676;'>&#10004; Conversion Complete!</strong>";
    optProgressDetails.textContent = "Input: " + srcSizeStr + " &rarr; Output: " + outSizeStr + redStr;

    showToast("Optimization complete: " + task.target_file);
    loadFilesList();

    setTimeout(function () {
      closeOptimizeModal();
    }, 2500);
  } else if (task.status === "failed") {
    clearInterval(taskPollTimer);
    taskPollTimer = null;
    activeTaskId = null;

    optStatusText.innerHTML = "<strong style='color:#ff7b72;'>&#10008; Conversion Failed</strong>";
    optProgressDetails.textContent = task.error || "Unknown FFmpeg error.";
    optBtnSubmit.disabled = false;
  }
}

// ----------------------------------------------------------------------
// Copy Download Link (With HTTP Fallback)
// ----------------------------------------------------------------------
function copyDownloadUrl(url) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(url).then(function () {
      showToast("Download URL copied to clipboard!");
    }).catch(function () {
      copyUsingExecCommand(url);
    });
  } else {
    copyUsingExecCommand(url);
  }
}

function copyUsingExecCommand(text) {
  var helper = document.getElementById("copy-helper");
  if (!helper) {
    helper = document.createElement("textarea");
    helper.id = "copy-helper";
    helper.style.position = "fixed";
    helper.style.top = "-9999px";
    document.body.appendChild(helper);
  }
  helper.value = text;
  helper.select();
  try {
    var successful = document.execCommand("copy");
    if (successful) {
      showToast("Download URL copied to clipboard!");
    } else {
      showToast("Please copy manually: " + text);
    }
  } catch (err) {
    showToast("Please copy manually: " + text);
  }
}

// ----------------------------------------------------------------------
// Delete File
// ----------------------------------------------------------------------
function deleteFile(filename) {
  if (!confirm("Are you sure you want to delete '" + filename + "' from the server?")) {
    return;
  }

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/delete", true);
  xhr.setRequestHeader("Content-Type", "application/json; charset=utf-8");

  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success) {
          showToast("Deleted: " + filename);
          loadFilesList();
        } else {
          showAlert("Delete failed: " + (resp.error || "Unknown error"), "error");
        }
      } catch (e) {
        showAlert("Failed to parse delete response", "error");
      }
    } else {
      var errMsg = "Delete failed with status " + xhr.status;
      try {
        var errResp = JSON.parse(xhr.responseText);
        if (errResp.error) errMsg = errResp.error;
      } catch (e) {}
      showAlert(errMsg, "error");
    }
  };

  xhr.onerror = function () {
    showAlert("Network error during file deletion", "error");
  };

  xhr.send(JSON.stringify({ filename: filename }));
}

// ----------------------------------------------------------------------
// Filtering
// ----------------------------------------------------------------------
function filterAdminList() {
  var input = document.getElementById("admin-search");
  if (!input) return;
  var term = input.value.toLowerCase();

  var filtered = filesList.filter(function (file) {
    return file.name.toLowerCase().indexOf(term) > -1;
  });

  renderMusicTable(filtered);
}

// ----------------------------------------------------------------------
// UI Helpers
// ----------------------------------------------------------------------
function showAlert(message, type) {
  if (!alertBox) return;
  alertBox.className = "alert alert-" + (type === "success" ? "success" : "error");
  alertBox.textContent = message;
  alertBox.style.display = "block";

  if (type === "success") {
    setTimeout(function () {
      alertBox.style.display = "none";
    }, 5000);
  }
}

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

function escapeJsString(str) {
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}
