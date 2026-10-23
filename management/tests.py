from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from management.git_sync import get_git_status

User = get_user_model()


class GitSyncSecurityAndFunctionalityTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="admin_staff",
            email="staff@uconnect.test",
            password="securepassword123",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="student_regular",
            email="student@uconnect.test",
            password="securepassword123",
            is_staff=False,
        )

    def test_git_status_anonymous_access_denied(self):
        """Anonymous users must be redirected away from git status API."""
        url = reverse("management:api_git_status")
        response = self.client.get(url)
        # staff_member_required redirects unauthenticated users
        self.assertEqual(response.status_code, 302)

    def test_git_status_regular_user_access_denied(self):
        """Regular non-staff users must not access git status API."""
        self.client.login(username="student_regular", password="securepassword123")
        url = reverse("management:api_git_status")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_git_status_staff_user_access_granted(self):
        """Staff members can access git status and receive valid JSON."""
        self.client.login(username="admin_staff", password="securepassword123")
        url = reverse("management:api_git_status")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("local_commit", data)
        self.assertIn("branch", data)
        self.assertIn("has_changes", data)

    def test_git_sync_unauthorized_post_rejected(self):
        """Anonymous or regular users cannot trigger git sync API."""
        url = reverse("management:api_git_sync")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 403)

    def test_git_sync_webhook_token_authorized(self):
        """Valid webhook secret token allows deployment call."""
        url = reverse("management:api_git_sync") + "?token=uconnect-deploy-cpanel-secret-2026"
        # Mock perform_git_sync to prevent running actual git pull during tests
        from unittest.mock import patch
        with patch("management.views.perform_git_sync") as mock_sync:
            mock_sync.return_value = {
                "success": True,
                "message": "Mocked sync success",
                "new_commit": "abc1234",
                "steps": [],
            }
            response = self.client.post(url, {})
            self.assertEqual(response.status_code, 200)
            mock_sync.assert_called_once()

    def test_get_git_status_function(self):
        """Verify get_git_status returns a clean dictionary."""
        status = get_git_status(force_refresh=True)
        self.assertEqual(status["status"], "success")
        self.assertTrue(len(status["local_commit"]) >= 4)
        self.assertIn("branch", status)
