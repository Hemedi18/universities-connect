/**
 * Screenshot-style multi-file uploader (max N files).
 * Uses DataTransfer to keep a staged FileList on the real input.
 */
(function () {
  function formatBytes(n) {
    if (!n && n !== 0) return "";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(0) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function initUploader(root) {
    const input = root.querySelector(".fu-input");
    const dropzone = root.querySelector(".fu-dropzone");
    const browse = root.querySelector(".fu-browse");
    const pending = root.querySelector(".fu-pending");
    const pendingThumbs = root.querySelector(".fu-pending-thumbs");
    const pendingTitle = root.querySelector(".fu-pending-title");
    const pendingCount = root.querySelector(".fu-pending-count");
    const progress = root.querySelector(".fu-progress span");
    const errorEl = root.querySelector(".fu-error");
    const recentCount = root.querySelector(".fu-recent-count");
    const max = parseInt(root.getAttribute("data-max") || "6", 10);
    const multiple = root.getAttribute("data-multiple") !== "0";
    let existing = parseInt(root.getAttribute("data-existing") || "0", 10);
    let staged = [];

    if (!input || !dropzone) return;

    function showError(msg) {
      if (!errorEl) return;
      if (!msg) {
        errorEl.hidden = true;
        errorEl.textContent = "";
        return;
      }
      errorEl.hidden = false;
      errorEl.textContent = msg;
    }

    function markedRemovals() {
      return root.querySelectorAll(".fu-remove-check:checked").length;
    }

    function slotsLeft() {
      return Math.max(0, max - (existing - markedRemovals()) - staged.length);
    }

    function syncInput() {
      const dt = new DataTransfer();
      staged.forEach((f) => dt.items.add(f));
      input.files = dt.files;
    }

    function renderPending() {
      if (!pending) return;
      if (!staged.length) {
        pending.hidden = true;
        pendingThumbs.innerHTML = "";
        if (progress) progress.style.width = "0%";
        return;
      }
      pending.hidden = false;
      if (pendingTitle) pendingTitle.textContent = "Uploading " + staged.length + " file" + (staged.length > 1 ? "s" : "");
      if (pendingCount) pendingCount.textContent = staged.length + " selected";
      pendingThumbs.innerHTML = "";
      staged.forEach((file, idx) => {
        const mini = document.createElement("div");
        mini.className = "fu-mini";
        const url = URL.createObjectURL(file);
        if (file.type.startsWith("video/")) {
          const v = document.createElement("video");
          v.src = url;
          v.muted = true;
          v.playsInline = true;
          mini.appendChild(v);
        } else {
          const img = document.createElement("img");
          img.src = url;
          img.alt = "";
          mini.appendChild(img);
        }
        mini.title = file.name + " (" + formatBytes(file.size) + ") — click to remove";
        mini.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          staged.splice(idx, 1);
          syncInput();
          renderPending();
          showError("");
        });
        pendingThumbs.appendChild(mini);
      });
      if (progress) {
        const pct = Math.min(100, Math.round(((existing - markedRemovals() + staged.length) / max) * 100));
        progress.style.width = pct + "%";
      }
    }

    function addFiles(fileList) {
      showError("");
      const incoming = Array.from(fileList || []);
      if (!incoming.length) return;
      if (!multiple) {
        staged = incoming.slice(0, 1);
        syncInput();
        renderPending();
        return;
      }
      let left = slotsLeft();
      if (left <= 0) {
        showError("Maximum " + max + " files. Remove one to add more.");
        return;
      }
      const accepted = [];
      for (const file of incoming) {
        if (left <= 0) break;
        const isImg = file.type.startsWith("image/");
        const isVid = file.type.startsWith("video/");
        if (!isImg && !isVid) continue;
        accepted.push(file);
        left -= 1;
      }
      if (!accepted.length) {
        showError("Use image or video files only.");
        return;
      }
      if (accepted.length < incoming.length) {
        showError("Only " + accepted.length + " file(s) added (max " + max + ").");
      }
      staged = staged.concat(accepted);
      syncInput();
      renderPending();
    }

    browse && browse.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      input.click();
    });

    dropzone.addEventListener("click", function (e) {
      if (e.target === browse || e.target.closest(".fu-browse")) return;
      // input covers zone; keep for keyboard
    });

    input.addEventListener("change", function () {
      // Replace staged with new selection when user picks via OS dialog
      // (OS always returns a fresh FileList). Merge with capacity.
      const picked = Array.from(input.files || []);
      staged = [];
      syncInput();
      addFiles(picked);
    });

    ["dragenter", "dragover"].forEach((ev) => {
      dropzone.addEventListener(ev, function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("is-drag");
      });
    });
    ["dragleave", "drop"].forEach((ev) => {
      dropzone.addEventListener(ev, function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove("is-drag");
      });
    });
    dropzone.addEventListener("drop", function (e) {
      addFiles(e.dataTransfer && e.dataTransfer.files);
    });

    root.querySelectorAll(".fu-remove-check").forEach((cb) => {
      cb.addEventListener("change", function () {
        const row = cb.closest(".fu-recent-item");
        if (row) row.classList.toggle("is-marked", cb.checked);
        if (recentCount) {
          const left = existing - markedRemovals();
          recentCount.textContent = left + " item" + (left === 1 ? "" : "s");
        }
        renderPending();
        showError("");
      });
    });

    // Form guard: need at least one image for product sell forms
    const form = root.closest("form");
    if (form && root.getAttribute("data-require-image") === "1") {
      form.addEventListener("submit", function (e) {
        const keptExisting = existing - markedRemovals();
        const hasNewImage = staged.some((f) => f.type.startsWith("image/"));
        const hasExistingImage = Array.from(root.querySelectorAll(".fu-recent-item:not(.is-marked) img")).length > 0;
        if (!hasNewImage && !hasExistingImage && keptExisting === 0) {
          e.preventDefault();
          showError("Add at least one product photo.");
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".fu-uploader").forEach(initUploader);
  });
})();
