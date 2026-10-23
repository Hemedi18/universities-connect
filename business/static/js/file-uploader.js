/**
 * Modern Collapsible Media Uploader with Trailing + Card & From Device / From URL Options
 */
(function () {
    let stagedFiles = [];
    let stagedUrls = [];

    document.addEventListener("DOMContentLoaded", function () {
        const container = document.getElementById("fuUploaderContainer");
        if (!container) return;

        const maxFiles = parseInt(container.getAttribute("data-max") || "6", 10);
        const fileInput = document.getElementById("id_media_files");
        const initialZone = document.getElementById("fuInitialZone");
        const galleryZone = document.getElementById("fuGalleryZone");
        const cardsGrid = document.getElementById("fuCardsGrid");
        const cardAddMore = document.getElementById("fuCardAddMore");
        const countDisplay = document.getElementById("fuCountDisplay");
        const slotRemaining = document.getElementById("fuSlotRemaining");
        const errorMsg = document.getElementById("fuErrorMsg");
        const urlInputsContainer = document.getElementById("fuUrlInputsContainer");

        // Modals
        const choiceModal = document.getElementById("fuChoiceModal");
        const urlModal = document.getElementById("fuUrlModal");
        const closeChoiceModal = document.getElementById("fuCloseChoiceModal");
        const closeUrlModal = document.getElementById("fuCloseUrlModal");
        const cancelUrlBtn = document.getElementById("fuCancelUrlBtn");

        // Buttons
        const pickDeviceBtn = document.getElementById("fuPickDeviceBtn");
        const pickUrlBtn = document.getElementById("fuPickUrlBtn");
        const choiceDeviceBtn = document.getElementById("fuChoiceDeviceBtn");
        const choiceUrlBtn = document.getElementById("fuChoiceUrlBtn");
        const submitUrlBtn = document.getElementById("fuSubmitUrlBtn");
        const urlInput = document.getElementById("fuUrlInput");
        const urlPreviewBox = document.getElementById("fuUrlPreviewBox");
        const urlImgPreview = document.getElementById("fuUrlImgPreview");
        const urlError = document.getElementById("fuUrlError");

        function showError(msg) {
            if (!errorMsg) return;
            if (msg) {
                errorMsg.textContent = msg;
                errorMsg.classList.remove("d-none");
            } else {
                errorMsg.textContent = "";
                errorMsg.classList.add("d-none");
            }
        }

        function getExistingCount() {
            return cardsGrid ? cardsGrid.querySelectorAll(".fu-existing-card").length : 0;
        }

        function getTotalCount() {
            return getExistingCount() + stagedFiles.length + stagedUrls.length;
        }

        function syncInputFiles() {
            if (!fileInput) return;
            const dt = new DataTransfer();
            stagedFiles.forEach(f => dt.items.add(f));
            fileInput.files = dt.files;
            
            // Trigger change on fileInput so live product preview card updates
            const ev = new Event("change", { bubbles: true });
            fileInput.dispatchEvent(ev);
        }

        function syncUrlInputs() {
            if (!urlInputsContainer) return;
            urlInputsContainer.innerHTML = "";
            stagedUrls.forEach(url => {
                const hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = "media_urls";
                hidden.value = url;
                urlInputsContainer.appendChild(hidden);
            });
        }

        function updateBuyerPreview() {
            const previewImg = document.getElementById("previewImg");
            if (!previewImg) return;

            // Find first image from DOM cards
            const firstImg = cardsGrid ? cardsGrid.querySelector(".fu-media-thumb img") : null;
            if (firstImg && firstImg.src) {
                previewImg.src = firstImg.src;
            }
        }

        function renderState() {
            const total = getTotalCount();
            if (countDisplay) countDisplay.textContent = total;
            const remaining = Math.max(0, maxFiles - total);
            if (slotRemaining) slotRemaining.textContent = `(${remaining} zimebaki)`;

            if (total === 0) {
                if (initialZone) initialZone.style.display = "block";
                if (galleryZone) galleryZone.style.display = "none";
            } else {
                if (initialZone) initialZone.style.display = "none";
                if (galleryZone) galleryZone.style.display = "block";

                // Position trailing + button at the very end
                if (cardAddMore) {
                    if (total >= maxFiles) {
                        cardAddMore.style.display = "none";
                    } else {
                        cardAddMore.style.display = "flex";
                        // Ensure cardAddMore is last child in grid
                        cardsGrid.appendChild(cardAddMore);
                    }
                }
            }
            updateBuyerPreview();
        }

        function addFiles(files) {
            showError("");
            const remaining = maxFiles - getTotalCount();
            if (remaining <= 0) {
                showError(`Umeshajaza idadi ya juu kabisa (Picha/Video ${maxFiles}).`);
                return;
            }

            const incoming = Array.from(files || []);
            let countAdded = 0;

            for (const file of incoming) {
                if (getTotalCount() >= maxFiles) break;
                const isImg = file.type.startsWith("image/");
                const isVid = file.type.startsWith("video/");
                if (!isImg && !isVid) continue;

                stagedFiles.push(file);
                countAdded++;

                // Create DOM card
                const card = document.createElement("div");
                card.className = "fu-media-card fu-staged-file-card";
                card.dataset.index = stagedFiles.length - 1;

                const thumb = document.createElement("div");
                thumb.className = "fu-media-thumb";
                const objUrl = URL.createObjectURL(file);

                if (isVid) {
                    const video = document.createElement("video");
                    video.src = objUrl;
                    video.muted = true;
                    video.playsInline = true;
                    thumb.appendChild(video);
                    const badge = document.createElement("span");
                    badge.className = "fu-play-badge";
                    badge.innerHTML = '<i class="bi bi-play-fill"></i>';
                    thumb.appendChild(badge);
                } else {
                    const img = document.createElement("img");
                    img.src = objUrl;
                    img.alt = file.name;
                    thumb.appendChild(img);
                }

                const coverBadge = document.createElement("div");
                coverBadge.className = "fu-card-badge-cover";
                coverBadge.textContent = "⭐ Cover";

                const removeBtn = document.createElement("button");
                removeBtn.type = "button";
                removeBtn.className = "fu-card-remove-btn";
                removeBtn.title = "Futa picha hii";
                removeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';

                removeBtn.addEventListener("click", function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    const idx = stagedFiles.indexOf(file);
                    if (idx > -1) {
                        stagedFiles.splice(idx, 1);
                    }
                    card.remove();
                    syncInputFiles();
                    renderState();
                });

                card.appendChild(thumb);
                card.appendChild(coverBadge);
                card.appendChild(removeBtn);

                // Insert before the + card
                cardsGrid.insertBefore(card, cardAddMore);
            }

            syncInputFiles();
            renderState();

            if (incoming.length > countAdded && countAdded < incoming.length) {
                showError(`Picha ${countAdded} zimeongezwa (Hadi faili ${maxFiles} tu zinaruhusiwa).`);
            }
        }

        function addUrlMedia(url) {
            showError("");
            if (getTotalCount() >= maxFiles) {
                showError(`Umeshajaza idadi ya juu kabisa (Picha/Video ${maxFiles}).`);
                return;
            }

            stagedUrls.push(url);

            const card = document.createElement("div");
            card.className = "fu-media-card fu-staged-url-card";

            const thumb = document.createElement("div");
            thumb.className = "fu-media-thumb";

            const isVid = url.match(/\.(mp4|webm|mov)(\?.*)?$/i);
            if (isVid) {
                const video = document.createElement("video");
                video.src = url;
                video.muted = true;
                video.playsInline = true;
                thumb.appendChild(video);
                const badge = document.createElement("span");
                badge.className = "fu-play-badge";
                badge.innerHTML = '<i class="bi bi-play-fill"></i>';
                thumb.appendChild(badge);
            } else {
                const img = document.createElement("img");
                img.src = url;
                img.alt = "URL Image";
                thumb.appendChild(img);
            }

            const coverBadge = document.createElement("div");
            coverBadge.className = "fu-card-badge-cover";
            coverBadge.textContent = "⭐ Cover";

            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "fu-card-remove-btn";
            removeBtn.title = "Futa picha hii";
            removeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';

            removeBtn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                const idx = stagedUrls.indexOf(url);
                if (idx > -1) {
                    stagedUrls.splice(idx, 1);
                }
                card.remove();
                syncUrlInputs();
                renderState();
            });

            card.appendChild(thumb);
            card.appendChild(coverBadge);
            card.appendChild(removeBtn);

            cardsGrid.insertBefore(card, cardAddMore);

            syncUrlInputs();
            renderState();
        }

        // Global function for existing media deletion
        window.removeExistingMedia = function (mediaId, btn) {
            const card = btn.closest(".fu-existing-card");
            if (card) {
                card.remove();
            }
            const removeContainer = document.getElementById("fuRemoveInputsContainer");
            if (removeContainer) {
                const hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = "remove_media_ids";
                hidden.value = mediaId;
                removeContainer.appendChild(hidden);
            }
            renderState();
        };

        // File picker listener
        if (fileInput) {
            fileInput.addEventListener("change", function () {
                if (this.files && this.files.length) {
                    addFiles(this.files);
                }
            });
        }

        // Buttons trigger
        pickDeviceBtn && pickDeviceBtn.addEventListener("click", () => fileInput && fileInput.click());
        choiceDeviceBtn && choiceDeviceBtn.addEventListener("click", () => {
            choiceModal.classList.add("d-none");
            fileInput && fileInput.click();
        });

        // Open URL modal
        function openUrlModal() {
            choiceModal.classList.add("d-none");
            urlModal.classList.remove("d-none");
            if (urlInput) {
                urlInput.value = "";
                urlInput.focus();
            }
            if (urlPreviewBox) urlPreviewBox.classList.add("d-none");
            if (urlError) urlError.classList.add("d-none");
        }

        pickUrlBtn && pickUrlBtn.addEventListener("click", openUrlModal);
        choiceUrlBtn && choiceUrlBtn.addEventListener("click", openUrlModal);

        // Open Choice modal on + card click
        cardAddMore && cardAddMore.addEventListener("click", function () {
            choiceModal.classList.remove("d-none");
        });

        // Close Modals
        closeChoiceModal && closeChoiceModal.addEventListener("click", () => choiceModal.classList.add("d-none"));
        closeUrlModal && closeUrlModal.addEventListener("click", () => urlModal.classList.add("d-none"));
        cancelUrlBtn && cancelUrlBtn.addEventListener("click", () => urlModal.classList.add("d-none"));

        choiceModal && choiceModal.addEventListener("click", function (e) {
            if (e.target === choiceModal) choiceModal.classList.add("d-none");
        });
        urlModal && urlModal.addEventListener("click", function (e) {
            if (e.target === urlModal) urlModal.classList.add("d-none");
        });

        // URL Live input preview
        if (urlInput) {
            urlInput.addEventListener("input", function () {
                const val = this.value.trim();
                if (val.startsWith("http://") || val.startsWith("https://")) {
                    if (urlImgPreview) urlImgPreview.src = val;
                    if (urlPreviewBox) urlPreviewBox.classList.remove("d-none");
                    if (urlError) urlError.classList.add("d-none");
                } else {
                    if (urlPreviewBox) urlPreviewBox.classList.add("d-none");
                }
            });
        }

        // Submit URL button
        submitUrlBtn && submitUrlBtn.addEventListener("click", function () {
            const val = urlInput ? urlInput.value.trim() : "";
            if (!val || !(val.startsWith("http://") || val.startsWith("https://"))) {
                if (urlError) urlError.classList.remove("d-none");
                return;
            }
            addUrlMedia(val);
            urlModal.classList.add("d-none");
        });

        // Drag and Drop support
        const dropCard = document.getElementById("fuDropCard");
        if (dropCard) {
            ["dragenter", "dragover"].forEach(ev => {
                dropCard.addEventListener(ev, e => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropCard.classList.add("is-drag");
                });
            });
            ["dragleave", "drop"].forEach(ev => {
                dropCard.addEventListener(ev, e => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropCard.classList.remove("is-drag");
                });
            });
            dropCard.addEventListener("drop", e => {
                const files = e.dataTransfer.files;
                if (files && files.length) {
                    addFiles(files);
                }
            });
        }

        // Initial setup
        renderState();
    });
})();
