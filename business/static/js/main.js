document.addEventListener('DOMContentLoaded', function() {
    
    // --- Navigation Toggler (Hamburger) ---
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.navbar-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', function() {
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
        });
    }

    // --- Theme Toggler ---
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const body = document.body;

    // Check for saved theme or system preference
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark-mode' || (!savedTheme && systemPrefersDark)) {
        body.classList.add('dark-mode');
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            body.classList.toggle('dark-mode');
            
            // Add animation class
            themeToggleBtn.classList.add('theme-toggle-anim');
            
            // Remove animation class after it finishes
            setTimeout(() => {
                themeToggleBtn.classList.remove('theme-toggle-anim');
            }, 500);

            // Save preference
            const isDarkMode = body.classList.contains('dark-mode');
            localStorage.setItem('theme', isDarkMode ? 'dark-mode' : 'light-mode');
        });
    }

    // --- Item Detail: Change Main Image ---
    const thumbnails = document.querySelectorAll('.thumbnail');
    const mainImage = document.querySelector('.product-image-large');
    
    if (thumbnails.length > 0 && mainImage) {
        thumbnails.forEach(thumb => {
            thumb.addEventListener('click', function() {
                mainImage.src = this.src;
                thumbnails.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
            });
        });
    }

    // --- About Page: Animations ---
    const animateElements = document.querySelectorAll('.animate-on-scroll');
    if (animateElements.length > 0) {
        // Hide elements initially via JS to ensure they are visible if JS fails
        animateElements.forEach(el => el.classList.add('js-hidden'));

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    const statNumber = entry.target.querySelector('.stat-number');
                    if (statNumber) {
                        const target = parseInt(statNumber.getAttribute('data-target'));
                        if (isNaN(target)) return; // Safety check
                        let count = 0;
                        const duration = 2000;
                        const increment = target / (duration / 16);
                        const timer = setInterval(() => {
                            count += increment;
                            if (count >= target) {
                                statNumber.textContent = target + "+";
                                clearInterval(timer);
                            } else {
                                statNumber.textContent = Math.floor(count);
                            }
                        }, 16);
                    }
                }
            });
        }, { threshold: 0.1 });

        animateElements.forEach(el => observer.observe(el));
    }

    // --- Post Item: Contact Method Toggle ---
    const methodField = document.querySelector('#id_contact_method');
    if (methodField) {
        const emailField = document.querySelector('#id_contact_email');
        const phoneField = document.querySelector('#id_contact_phone');
        
        function getContainer(field) {
            return field ? field.closest('.form-group') : null;
        }

        function updateFields() {
            const method = methodField.value;
            const emailContainer = getContainer(emailField);
            const phoneContainer = getContainer(phoneField);

            if(emailContainer) emailContainer.style.display = 'none';
            if(phoneContainer) phoneContainer.style.display = 'none';

            if (method === 'email' && emailContainer) {
                emailContainer.style.display = 'block';
            } else if (method === 'phone' && phoneContainer) {
                phoneContainer.style.display = 'block';
            }
        }

        methodField.addEventListener('change', updateFields);
        updateFields();
    }

    // --- Register: Error Fade Out ---
    const errors = document.querySelectorAll('.error-message');
    if (errors.length > 0) {
        setTimeout(function() {
            errors.forEach(function(error) {
                error.style.transition = 'opacity 0.5s ease';
                error.style.opacity = '0';
                setTimeout(() => error.remove(), 500);
            });
        }, 5000);
    }

    // --- User Dashboard: Tabs ---
    const tabLinks = document.querySelectorAll('.tab-link');
    if (tabLinks.length > 0) {
        tabLinks.forEach(link => {
            link.addEventListener('click', function(evt) {
                const tabName = this.getAttribute('data-tab');
                document.querySelectorAll('.tab-content').forEach(tab => tab.style.display = 'none');
                document.querySelectorAll('.tab-link').forEach(l => l.classList.remove('active'));
                document.getElementById(tabName).style.display = 'block';
                this.classList.add('active');
            });
        });
    }

    // --- Chat Room Logic ---
    const messagesContainer = document.getElementById('messagesContainer');
    if (messagesContainer) {
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        window.addEventListener('resize', function() {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        });

        const input = document.querySelector('.chat-input-area input');
        if(input) input.focus();

        const form = document.querySelector('.chat-input-area form');
        const currentUserId = messagesContainer.getAttribute('data-user-id');
        const conversationId = messagesContainer.getAttribute('data-conversation-id');
        const getMessagesUrl = messagesContainer.getAttribute('data-url');

        function getTickHtml(status) {
            let tickClass = 'tick-sent';
            // SVG for single tick (Check)
            let svgContent = '<path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>';
            
            if (status === 'delivered' || status === 'read') {
                // SVG for double tick (Done All)
                svgContent = '<path fill="currentColor" d="M18 7l-1.41-1.41-6.34 6.34 1.41 1.41L18 7zm4.24-1.41L11.66 16.17 7.48 12l-1.41 1.41L11.66 19l12-12-1.42-1.41zM.41 13.41L6 19l1.41-1.41L1.83 12 .41 13.41z"/>';
                tickClass = (status === 'read') ? 'tick-read' : 'tick-delivered';
            }
            return `<span class="tick-icon ${tickClass}"><svg xmlns="http://www.w3.org/2000/svg" height="16" viewBox="0 0 24 24" width="16">${svgContent}</svg></span>`;
        }

        function appendMessage(msg) {
            if(document.querySelector(`.message-bubble[data-id="${msg.id}"]`)) return;
            const div = document.createElement('div');
            const isSent = msg.sender_id == currentUserId || msg.is_sent;
            div.className = `message-bubble ${isSent ? 'sent' : 'received'}`;
            div.dataset.id = msg.id;
            
            let ticks = '';
            if (isSent) {
                ticks = getTickHtml(msg.status || 'sent');
            }
            div.innerHTML = `<div class="message-content">${msg.content}</div><div class="message-time">${msg.timestamp}${ticks}</div>`;
            messagesContainer.appendChild(div);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(form);
                fetch("", { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": formData.get('csrfmiddlewaretoken') }, body: formData })
                .then(response => response.json())
                .then(data => { if(data.status === 'success') { appendMessage(data.message); form.reset(); } });
            });
        }

        if (getMessagesUrl) {
            const fetchMessages = () => {
                const lastMsg = messagesContainer.querySelector('.message-bubble:last-child');
                // Ensure lastId is valid; if data-id is missing/undefined, default to 0 to prevent server errors
                const lastId = (lastMsg && lastMsg.dataset.id) ? lastMsg.dataset.id : 0;
                fetch(`${getMessagesUrl}?last_id=${lastId}`)
                .then(res => res.json())
                .then(data => { 
                    if(data.messages && data.messages.length > 0) {
                        data.messages.forEach(msg => appendMessage(msg)); 
                    }
                    if(data.statuses) {
                        data.statuses.forEach(st => {
                            const bubble = document.querySelector(`.message-bubble[data-id="${st.id}"]`);
                            if (bubble && bubble.classList.contains('sent')) {
                                const timeDiv = bubble.querySelector('.message-time');
                                if (timeDiv) {
                                    const existingTick = timeDiv.querySelector('.tick-icon');
                                    if(existingTick) existingTick.remove();
                                    timeDiv.insertAdjacentHTML('beforeend', getTickHtml(st.status));
                                }
                            }
                        });
                    }
                    
                    // Update Header Status (Online/Offline)
                    if (data.partner) {
                        const header = document.querySelector('.chat-room-header');
                        if (header) {
                            // Check if we need to restructure header for the new layout
                            let userContainer = header.querySelector('.header-user-container');
                            if (!userContainer) {
                                // Get existing elements
                                const backBtn = header.querySelector('.back-btn');
                                const nameEl = header.querySelector('.chat-username');
                                const nameText = nameEl ? nameEl.textContent : data.partner.name;
                                
                                // Create new structure
                                if (nameEl) nameEl.remove();
                                
                                const avatarUrl = data.partner.avatar || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(nameText) + '&background=random';
                                
                                const html = `
                                    <div class="header-user-container">
                                        <img src="${avatarUrl}" class="header-profile-pic" alt="Profile">
                                        <div class="chat-username">${nameText}</div>
                                        <div class="header-status">
                                            <span class="status-dot ${data.partner.is_online ? 'online' : 'offline'}"></span>
                                            <span class="status-text">${data.partner.is_online ? 'Active' : 'Inactive'}</span>
                                        </div>
                                    </div>
                                `;
                                if (backBtn) backBtn.insertAdjacentHTML('afterend', html);
                            } else {
                                // Just update status
                                const dot = header.querySelector('.status-dot');
                                const text = header.querySelector('.status-text');
                                if (dot) {
                                    dot.className = `status-dot ${data.partner.is_online ? 'online' : 'offline'}`;
                                }
                                if (text) {
                                    text.textContent = data.partner.is_online ? 'Active' : 'Inactive';
                                }
                            }
                        }
                    }
                });
            };
            
            // Run immediately to update existing messages
            fetchMessages();
            // Poll every 2 seconds
            setInterval(fetchMessages, 2000);
        }
    }

    // --- Global: Delete Confirmation ---
    document.body.addEventListener('click', function(e) {
        // Check if the clicked element or its parent has the delete-item-btn class
        if (e.target.closest('.delete-item-btn')) {
            if (!confirm('Are you sure you want to delete this item?')) {
                e.preventDefault();
            }
        }
    });

    // --- Cart: Checkout Alert ---
    const checkoutBtn = document.querySelector('.btn-checkout');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', function() {
            alert('Checkout functionality coming soon!');
        });
    }

    // --- Page Specific Body Classes (to replace internal CSS targeting parents) ---
    if (document.querySelector('.chat-room-container')) {
        document.body.classList.add('page-chat-room');
    }
    if (document.querySelector('.home-container-mobile')) {
        document.body.classList.add('page-home-mobile');
    }
    if (document.querySelector('.about-container-override')) {
        document.body.classList.add('page-about');
    }
    if (document.querySelector('.container-mobile-full')) {
        document.body.classList.add('page-sell-mobile');
    }

    // --- Global: Unread Messages Badge ---
    function updateUnreadCount() {
        fetch('/chat/api/unread/')
            .then(response => response.json())
            .then(data => {
                const count = data.count;
                // Find chat link in navbar - assuming it contains 'chat' or 'inbox' in href
                const chatLinks = document.querySelectorAll('a[href*="/chat/"]');
                chatLinks.forEach(link => {
                    let badge = link.querySelector('.nav-badge');
                    if (count > 0) {
                        if (!badge) {
                            badge = document.createElement('span');
                            badge.className = 'nav-badge';
                            link.appendChild(badge);
                            link.style.position = 'relative'; // Ensure positioning context
                        }
                        badge.textContent = count;
                        badge.style.display = 'flex';
                    } else if (badge) {
                        badge.style.display = 'none';
                    }
                });
            })
            .catch(err => console.log('Error fetching unread count:', err));
    }
    
    // Poll every 5 seconds if user is logged in (check if chat link exists)
    if (document.querySelector('a[href*="/chat/"]')) {
        updateUnreadCount();
        setInterval(updateUnreadCount, 5000);
    }

    // --- Chat Room: Mobile Keyboard Fix ---
    // Uses visualViewport API to resize container when keyboard pushes screen up
    if (window.visualViewport && document.querySelector('.chat-room-container')) {
        const chatContainer = document.querySelector('.chat-room-container');
        const msgContainer = document.getElementById('messagesContainer');
        
        const resizeHandler = () => {
            if (window.innerWidth <= 768) {
                // Calculate visible height minus header (approx 70px)
                const height = window.visualViewport.height; // Full height as main header is hidden
                chatContainer.style.height = `${height}px`;
                if (msgContainer) msgContainer.scrollTop = msgContainer.scrollHeight;
            }
        };

        window.visualViewport.addEventListener('resize', resizeHandler);
    }

    // --- Sell Page: Multi-step Wizard ---
    const sellForm = document.querySelector('.sell-container form');
    if (sellForm) {
        // Wrap existing form groups into steps
        const groups = Array.from(sellForm.querySelectorAll('.form-group'));
        if (groups.length > 0) {
            // Create Step Containers
            const step1 = document.createElement('div'); step1.className = 'wizard-step active'; step1.dataset.step = '1';
            const step2 = document.createElement('div'); step2.className = 'wizard-step'; step2.dataset.step = '2';
            const step3 = document.createElement('div'); step3.className = 'wizard-step'; step3.dataset.step = '3';

            step1.innerHTML = '<h3 class="step-title" style="margin-bottom:1rem; grid-column:1/-1;">Step 1: Basic Information</h3>';
            step2.innerHTML = '<h3 class="step-title" style="margin-bottom:1rem; grid-column:1/-1;">Step 2: Detailed Specifications</h3>';
            step3.innerHTML = '<h3 class="step-title" style="margin-bottom:1rem; grid-column:1/-1;">Step 3: Payment & Order Details</h3>';

            // Distribute fields based on name or data attribute
            groups.forEach(group => {
                const input = group.querySelector('input, select, textarea');
                if (!input) return;
                const name = input.name;
                
                // Step 1: Basic Info (Title, Condition, Image, Brand/Make)
                if (['title', 'condition', 'image'].includes(name) || input.getAttribute('data-wizard-step') === '1') {
                    step1.appendChild(group);
                }
                // Step 3: Payment & Order (Price, Stock, Min Order, Shipping, Contact)
                else if (['price', 'compare_at_price', 'stock_quantity', 'minimum_order_quantity', 'contact_method', 'contact_email', 'contact_phone', 'image2', 'image3', 'sku', 'tax_class', 'shipping_weight', 'shipping_dimensions'].includes(name)) {
                    step3.appendChild(group);
                }
                // Step 2: Detailed Info (Description, Location, Attributes)
                else {
                    step2.appendChild(group);
                }
            });
            
            // Insert Steps
            const submitBtn = sellForm.querySelector('.btn-submit');
            sellForm.insertBefore(step1, submitBtn);
            sellForm.insertBefore(step2, submitBtn);
            sellForm.insertBefore(step3, submitBtn);

            // Create Navigation Buttons
            const navDiv = document.createElement('div');
            navDiv.className = 'wizard-nav';
            navDiv.innerHTML = `
                <button type="button" class="btn-prev" style="display:none;">Previous</button>
                <button type="button" class="btn-next">Next</button>
            `;
            sellForm.insertBefore(navDiv, submitBtn);

            // Hide Submit initially
            submitBtn.style.display = 'none';

            // Wizard Logic
            let currentStep = 1;
            const totalSteps = 3;
            
            // Auto-detect step with errors
            const steps = [step1, step2, step3];
            for (let i = 0; i < steps.length; i++) {
                if (steps[i].querySelector('.error-text-custom') || steps[i].querySelector('.errorlist')) {
                    currentStep = i + 1;
                    break;
                }
            }

            const prevBtn = navDiv.querySelector('.btn-prev');
            const nextBtn = navDiv.querySelector('.btn-next');

            function updateWizard() {
                document.querySelectorAll('.wizard-step').forEach(s => {
                    s.style.display = s.dataset.step == currentStep ? '' : 'none';
                });

                prevBtn.style.display = currentStep === 1 ? 'none' : 'inline-block';
                
                if (currentStep === totalSteps) {
                    nextBtn.style.display = 'none';
                    submitBtn.style.display = 'block';
                } else {
                    nextBtn.style.display = 'inline-block';
                    submitBtn.style.display = 'none';
                }
            }

            nextBtn.addEventListener('click', () => {
                if(currentStep < totalSteps) {
                    currentStep++;
                    updateWizard();
                }
            });

            prevBtn.addEventListener('click', () => {
                if(currentStep > 1) {
                    currentStep--;
                    updateWizard();
                }
            });

            updateWizard(); // Init
        }
    }

    // --- Custom Datalist Logic ---
    const customDatalistContainers = document.querySelectorAll('.custom-datalist-container');
    
    customDatalistContainers.forEach(container => {
        const input = container.querySelector('input');
        const list = container.querySelector('.custom-datalist');
        
        if (!input || !list) return;
        
        const options = Array.from(list.querySelectorAll('.custom-option'));
        
        const filterOptions = () => {
            const filter = input.value.toLowerCase();
            let hasVisible = false;
            options.forEach(option => {
                const text = option.textContent.toLowerCase();
                if (text.includes(filter)) {
                    option.style.display = 'block';
                    hasVisible = true;
                } else {
                    option.style.display = 'none';
                }
            });
            list.classList.toggle('active', hasVisible);
        };

        input.addEventListener('focus', () => { list.classList.add('active'); filterOptions(); });
        input.addEventListener('input', () => { list.classList.add('active'); filterOptions(); });
        
        // Hide on click outside
        document.addEventListener('click', (e) => {
            if (!container.contains(e.target)) list.classList.remove('active');
        });
        
        // Handle option click
        list.addEventListener('click', (e) => {
            if (e.target.classList.contains('custom-option')) {
                input.value = e.target.getAttribute('data-value');
                list.classList.remove('active');
            }
        });
    });
});