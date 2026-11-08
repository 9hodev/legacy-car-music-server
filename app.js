/**
 * Local Music Drop Server - Admin Application JavaScript
 * Zero dependencies, Vanilla JS using XMLHttpRequest for progress tracking
 */

var filesList = [];
var isUploading = false;

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

  // Allow clicking drop-zone (outside of button) to browse
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
  var allowedExts = [".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg"];

  for (var i = 0; i < files.length; i++) {
    var file = files[i];
    var nameLower = file.name.toLowerCase();
    var hasValidExt = allowedExts.some(function (ext) {
      return nameLower.endsWith(ext);
    });

    if (hasValidExt) {
      validFiles.push(file);
    } else {
      showAlert("Skipped '" + file.name + "': Only audio files (.mp3, .m4a, .aac, .flac, .wav, .ogg) are supported.", "error");
    }
  }

  if (validFiles.length === 0) {
    return;
  }

  // Upload sequential files
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
      
      // Calculate speed
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
  xhr.open("GET", "/api/files", true);
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

    rowsHtml += '<tr>' +
      '<td>' +
        '<div class="song-cell-title">' +
          '<span class="song-icon">&#9835;</span>' +
          '<span>' + safeName + '</span>' +
        '</div>' +
      '</td>' +
      '<td>' + (file.size_formatted || formatBytes(file.size)) + '</td>' +
      '<td>' +
        '<div class="table-actions">' +
          '<button class="btn btn-secondary btn-small" onclick="copyDownloadUrl(\'' + escapeJsString(fullUrl) + '\')">' +
            '&#128203; Copy Link' +
          '</button>' +
          '<a class="btn btn-primary btn-small" href="' + file.url + '" download>' +
            '&#11015; Download' +
          '</a>' +
          '<button class="btn btn-danger btn-small" onclick="deleteFile(\'' + escapeJsString(file.name) + '\')">' +
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
// Copy Download Link (With HTTP Fallback)
// ----------------------------------------------------------------------
function copyDownloadUrl(url) {
  // Try modern Clipboard API if supported and available
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(url).then(function () {
      showToast("Download URL copied to clipboard!");
    }).catch(function () {
      copyUsingExecCommand(url);
    });
  } else {
    // Fallback for plain HTTP origins
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
      showAlert("Delete failed with status " + xhr.status, "error");
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

