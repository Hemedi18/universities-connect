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
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    const statNumber = entry.target.querySelector('.stat-number');
                    if (statNumber) {
                        const target = parseInt(statNumber.getAttribute('data-target'));
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

        function appendMessage(msg) {
            if(document.querySelector(`.message-bubble[data-id="${msg.id}"]`)) return;
            const div = document.createElement('div');
            const isSent = msg.sender_id == currentUserId || msg.is_sent;
            div.className = `message-bubble ${isSent ? 'sent' : 'received'}`;
            div.dataset.id = msg.id;
            div.innerHTML = `<div class="message-content">${msg.content}</div><div class="message-time">${msg.timestamp}</div>`;
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
            setInterval(() => {
                const lastMsg = messagesContainer.querySelector('.message-bubble:last-child');
                const lastId = lastMsg ? lastMsg.dataset.id : 0;
                fetch(`${getMessagesUrl}?last_id=${lastId}`).then(res => res.json()).then(data => { if(data.messages && data.messages.length > 0) data.messages.forEach(msg => appendMessage(msg)); });
            }, 2000);
        }
    }
});