import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from users.models import SupportSession, SupportMessage


class SupportChatTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@u-connect.com",
            password="adminpassword123",
        )
        self.staff_user = User.objects.create_user(
            username="staff_responder",
            email="staff@u-connect.com",
            password="staffpassword123",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="student_user",
            email="student@univ.edu",
            password="studentpass123",
        )

    def test_guest_chat_initialization_and_welcome_message(self):
        """Unauthenticated visitor opens /support-chat/ from login page: session and welcome message are initialized."""
        response = self.client.get(reverse("guest_chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "U-Connect Support")
        self.assertContains(response, "Active responder ready")

        session_key = self.client.session.get("support_session_key")
        self.assertIsNotNone(session_key)

        session = SupportSession.objects.filter(session_key=session_key).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, "open")

        # Auto-welcome message from admin should exist
        messages = session.messages.all()
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.first().sender_type, "admin")
        self.assertIn("Welcome to U-Connect Support", messages.first().text)

    def test_guest_send_message_and_poll(self):
        """Guest sends a message and can poll to retrieve it."""
        # First visit to initialize session
        self.client.get(reverse("guest_chat"))

        # Send a guest message
        send_url = reverse("support_api_send")
        post_data = {
            "text": "Hello, I cannot login with my university account.",
            "guest_name": "Test Guest",
            "guest_email": "testguest@example.com",
        }
        res = self.client.post(
            send_url,
            data=json.dumps(post_data),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code, 200)
        json_res = res.json()
        self.assertEqual(json_res["status"], "success")
        self.assertEqual(json_res["message"]["sender_type"], "guest")
        self.assertEqual(json_res["message"]["text"], "Hello, I cannot login with my university account.")

        session_key = self.client.session.get("support_session_key")
        session = SupportSession.objects.get(session_key=session_key)
        self.assertEqual(session.guest_name, "Test Guest")
        self.assertEqual(session.guest_email, "testguest@example.com")
        self.assertEqual(session.messages.count(), 2)  # 1 welcome + 1 user message

        # Poll for messages
        poll_url = reverse("support_api_messages")
        poll_res = self.client.get(poll_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(poll_res.status_code, 200)
        poll_data = poll_res.json()
        self.assertEqual(poll_data["status"], "success")
        self.assertEqual(len(poll_data["messages"]), 2)

    def test_admin_responder_flow(self):
        """Admin views sessions in dashboard, opens chat console, and replies to guest."""
        # 1. Guest visits and asks for help
        guest_client = Client()
        guest_client.get(reverse("guest_chat"))
        guest_client.post(
            reverse("support_api_send"),
            data=json.dumps({"text": "Please reset my password"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        guest_session_key = guest_client.session.get("support_session_key")
        session = SupportSession.objects.get(session_key=guest_session_key)

        # 2. Regular user cannot access admin dashboard
        reg_client = Client()
        reg_client.login(username="student_user", password="studentpass123")
        res_reg = reg_client.get(reverse("admin_support_dashboard"))
        # Should redirect to login because not staff
        self.assertIn(res_reg.status_code, [302, 403])

        # 3. Staff user logs in and views dashboard
        admin_client = Client()
        admin_client.login(username="staff_responder", password="staffpassword123")
        dash_res = admin_client.get(reverse("admin_support_dashboard"))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, f"#{session.id}")
        self.assertContains(dash_res, "Please reset my password")

        # 4. Admin opens live console for this session
        chat_console_res = admin_client.get(reverse("admin_support_chat", args=[session.id]))
        self.assertEqual(chat_console_res.status_code, 200)
        self.assertContains(chat_console_res, f"Ticket #{session.id}")

        # Session should now be assigned to staff_responder
        session.refresh_from_db()
        self.assertEqual(session.assigned_admin, self.staff_user)

        # 5. Admin replies to guest
        admin_reply_res = admin_client.post(
            reverse("support_api_send"),
            data=json.dumps({
                "session_id": session.id,
                "text": "Hello! I have reset your password. Your temporary password is TempPass#2026.",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(admin_reply_res.status_code, 200)
        reply_json = admin_reply_res.json()
        self.assertEqual(reply_json["status"], "success")
        self.assertEqual(reply_json["message"]["sender_type"], "admin")
        self.assertEqual(reply_json["message"]["sender_badge"], "Admin Support")

        session.refresh_from_db()
        self.assertEqual(session.status, "in_progress")

        # 6. Guest polls and receives Admin's reply
        guest_poll = guest_client.get(reverse("support_api_messages"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(guest_poll.status_code, 200)
        guest_poll_data = guest_poll.json()
        admin_msgs = [m for m in guest_poll_data["messages"] if m["sender_type"] == "admin" and "TempPass#2026" in m["text"]]
        self.assertEqual(len(admin_msgs), 1)

    def test_admin_update_status(self):
        """Admin marks ticket as resolved and then reopens it."""
        guest_client = Client()
        guest_client.get(reverse("guest_chat"))
        guest_session_key = guest_client.session.get("support_session_key")
        session = SupportSession.objects.get(session_key=guest_session_key)

        admin_client = Client()
        admin_client.login(username="admin", password="adminpassword123")

        # Mark as resolved
        status_url = reverse("admin_support_update_status", args=[session.id])
        res = admin_client.post(status_url, {"status": "resolved"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["new_status"], "resolved")

        session.refresh_from_db()
        self.assertEqual(session.status, "resolved")

        # Reopen
        res2 = admin_client.post(status_url, {"status": "open"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["new_status"], "open")

        session.refresh_from_db()
        self.assertEqual(session.status, "open")

    def test_support_message_with_screenshot_and_page_url(self):
        """User/guest captures screenshot and submits complaint with page_url."""
        self.client.get(reverse("guest_chat"))

        # 1x1 transparent PNG data URI
        sample_screenshot_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        post_data = {
            "text": "Buttons are oversized on mobile help page",
            "screenshot": sample_screenshot_b64,
            "page_url": "https://uconnect.edusphere.co.tz/documentation/",
        }
        res = self.client.post(
            reverse("support_api_send"),
            data=json.dumps(post_data),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["message"]["image_url"].endswith(".png") or "/media/" in data["message"]["image_url"])
        self.assertEqual(data["message"]["page_url"], "https://uconnect.edusphere.co.tz/documentation/")

        # Poll messages and verify image_url is returned
        poll_res = self.client.get(reverse("support_api_messages"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(poll_res.status_code, 200)
        poll_data = poll_res.json()
        last_msg = poll_data["messages"][-1]
        self.assertIn("oversized on mobile", last_msg["text"])
        self.assertTrue(bool(last_msg["image_url"]))
        self.assertEqual(last_msg["page_url"], "https://uconnect.edusphere.co.tz/documentation/")

    def test_switch_admin_mode_toggle(self):
        """Staff user toggles between managed and normal mode via switch_mode."""
        self.client.login(username="admin", password="adminpassword123")

        # Switch to Normal Mode
        res_normal = self.client.get(reverse("management:switch_mode") + "?mode=normal")
        self.assertEqual(res_normal.status_code, 302)
        self.assertIn("/admin/?mode=normal", res_normal["Location"])
        self.assertEqual(res_normal.cookies["admin_mode"].value, "normal")

        # Switch to Managed Mode
        res_managed = self.client.get(reverse("management:switch_mode") + "?mode=managed")
        self.assertEqual(res_managed.status_code, 302)
        self.assertIn(reverse("management:dashboard"), res_managed["Location"])
        self.assertEqual(res_managed.cookies["admin_mode"].value, "managed")


from users.models import EmailOTP


class EmailOTPTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_registration_requires_email(self):
        """Registering without email fails validation."""
        res = self.client.post(
            reverse("users:register"),
            {
                "username": "newstudent123",
                "phone_number": "0712345678",
                "password": "Password123#",
                "confirm_password": "Password123#",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue("email" in res.context["form"].errors)

    def test_registration_flow_and_otp_verification(self):
        """User registers with email, receives OTP, verifies it, and is activated and logged in."""
        reg_data = {
            "username": "freshstudent",
            "email": "freshstudent@test.com",
            "phone_number": "0712345678",
            "password1": "SecurePass#2026",
            "password2": "SecurePass#2026",
        }
        res = self.client.post(reverse("users:register"), reg_data)
        # Should redirect to verify_otp
        self.assertRedirects(res, reverse("users:verify_otp"))

        # User should exist but be inactive pending verification
        user = User.objects.get(username="freshstudent")
        self.assertEqual(user.email, "freshstudent@test.com")
        self.assertFalse(user.is_active)
        self.assertFalse(user.profile.is_email_verified)

        # OTP should have been generated
        otp = EmailOTP.objects.filter(email="freshstudent@test.com", purpose="registration").first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.otp_code), 6)

        # Submit wrong OTP
        wrong_res = self.client.post(reverse("users:verify_otp"), {"otp_code": "000000"})
        self.assertEqual(wrong_res.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Submit correct OTP
        verify_res = self.client.post(reverse("users:verify_otp"), {"otp_code": otp.otp_code})
        self.assertRedirects(verify_res, reverse("customer:home"))

        # User is now active and verified!
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.profile.is_email_verified)

    def test_password_reset_flow_with_otp(self):
        """User requests password reset with email, receives OTP, and resets password."""
        user = User.objects.create_user(
            username="existinguser",
            email="existing@u-connect.com",
            password="OldPassword#1",
        )

        # 1. Request reset
        req_res = self.client.post(reverse("password_reset_request"), {"email": "existing@u-connect.com"})
        self.assertRedirects(req_res, reverse("password_reset_verify"))

        otp = EmailOTP.objects.filter(email="existing@u-connect.com", purpose="password_reset").first()
        self.assertIsNotNone(otp)

        # 2. Verify and set new password
        reset_res = self.client.post(
            reverse("password_reset_verify"),
            {
                "otp_code": otp.otp_code,
                "new_password": "NewSecretPassword#2",
                "confirm_password": "NewSecretPassword#2",
            },
        )
        self.assertRedirects(reset_res, reverse("users:login"))

        # 3. Old password fails, new password succeeds
        user.refresh_from_db()
        self.assertFalse(user.check_password("OldPassword#1"))
        self.assertTrue(user.check_password("NewSecretPassword#2"))

    def test_login_page_renders_forgot_password_and_error_popup(self):
        """Verify login page displays prominent forgot password options and renders error popup on invalid credentials."""
        # 1. GET login page contains forgot password links and chat support
        get_res = self.client.get(reverse("users:login"))
        self.assertEqual(get_res.status_code, 200)
        content = get_res.content.decode("utf-8")
        self.assertIn("Umesahau nenosiri", content)
        self.assertIn(reverse("password_reset_request"), content)
        self.assertIn(reverse("guest_chat"), content)

        # 2. POST with wrong password triggers error popup and non_field_errors banner
        bad_post = self.client.post(
            reverse("users:login"),
            {"username": "nonexistent_or_bad", "password": "wrongpassword123"},
        )
        self.assertEqual(bad_post.status_code, 200)
        bad_content = bad_post.content.decode("utf-8")
        # Ensure error message popup is in HTML
        self.assertIn("Imeshindwa kuingia", bad_content)
        self.assertIn("uc-toast-error", bad_content)
        # Ensure direct reset password link is displayed in the error card
        self.assertIn(reverse("password_reset_request"), bad_content)

    def test_login_with_email_address(self):
        """User can log in using their email address in place of username."""
        User.objects.create_user(
            username="studentalice",
            email="alice@campus.ac.tz",
            password="AliceSecurePass#2026",
            is_active=True,
        )

        res = self.client.post(
            reverse("users:login"),
            {"username": "alice@campus.ac.tz", "password": "AliceSecurePass#2026"},
        )
        self.assertRedirects(res, reverse("customer:home"))

