from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from rest_framework import status

from .models import KYCSubmission, UserProfile, NotificationEvent


class StateMachineUnitTests(TestCase):
    """Unit tests for the KYC state machine logic."""

    def setUp(self):
        self.user = User.objects.create_user(username='merchant1', password='pass123')
        UserProfile.objects.create(user=self.user, role='merchant')
        self.submission = KYCSubmission.objects.create(merchant=self.user)

    def test_legal_transition_draft_to_submitted(self):
        self.submission.transition_to(KYCSubmission.STATE_SUBMITTED)
        self.assertEqual(self.submission.state, KYCSubmission.STATE_SUBMITTED)
        self.assertIsNotNone(self.submission.submitted_at)

    def test_illegal_transition_draft_to_approved(self):
        """draft -> approved is illegal and must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.submission.transition_to(KYCSubmission.STATE_APPROVED)
        self.assertIn("Cannot transition", str(ctx.exception))

    def test_illegal_transition_approved_to_draft(self):
        """approved is a terminal state — no transitions allowed."""
        # Fast-track to approved via legal path
        self.submission.state = KYCSubmission.STATE_APPROVED
        self.submission.save()
        with self.assertRaises(ValueError):
            self.submission.transition_to(KYCSubmission.STATE_DRAFT)

    def test_illegal_transition_submitted_to_approved(self):
        """submitted -> approved skips under_review, must be rejected."""
        self.submission.transition_to(KYCSubmission.STATE_SUBMITTED)
        with self.assertRaises(ValueError):
            self.submission.transition_to(KYCSubmission.STATE_APPROVED)

    def test_full_legal_path_to_approved(self):
        """draft -> submitted -> under_review -> approved"""
        self.submission.transition_to(KYCSubmission.STATE_SUBMITTED)
        self.submission.transition_to(KYCSubmission.STATE_UNDER_REVIEW)
        self.submission.transition_to(KYCSubmission.STATE_APPROVED)
        self.assertEqual(self.submission.state, KYCSubmission.STATE_APPROVED)

    def test_more_info_path(self):
        """under_review -> more_info_requested -> submitted"""
        self.submission.transition_to(KYCSubmission.STATE_SUBMITTED)
        self.submission.transition_to(KYCSubmission.STATE_UNDER_REVIEW)
        self.submission.transition_to(KYCSubmission.STATE_MORE_INFO)
        self.submission.transition_to(KYCSubmission.STATE_SUBMITTED)
        self.assertEqual(self.submission.state, KYCSubmission.STATE_SUBMITTED)

    def test_rejected_is_terminal(self):
        self.submission.state = KYCSubmission.STATE_REJECTED
        self.submission.save()
        with self.assertRaises(ValueError):
            self.submission.transition_to(KYCSubmission.STATE_SUBMITTED)

    def test_can_transition_to_returns_false_for_illegal(self):
        self.assertFalse(self.submission.can_transition_to(KYCSubmission.STATE_APPROVED))
        self.assertFalse(self.submission.can_transition_to(KYCSubmission.STATE_UNDER_REVIEW))

    def test_can_transition_to_returns_true_for_legal(self):
        self.assertTrue(self.submission.can_transition_to(KYCSubmission.STATE_SUBMITTED))


class SLATrackingTests(TestCase):
    """Test the dynamic SLA at_risk computation."""

    def setUp(self):
        self.user = User.objects.create_user(username='merchant2', password='pass123')
        UserProfile.objects.create(user=self.user, role='merchant')

    def test_not_at_risk_when_fresh(self):
        sub = KYCSubmission.objects.create(
            merchant=self.user,
            state=KYCSubmission.STATE_SUBMITTED,
            submitted_at=timezone.now(),
        )
        self.assertFalse(sub.is_at_risk)

    def test_at_risk_when_old(self):
        sub = KYCSubmission.objects.create(
            merchant=self.user,
            state=KYCSubmission.STATE_SUBMITTED,
            submitted_at=timezone.now() - timezone.timedelta(hours=25),
        )
        self.assertTrue(sub.is_at_risk)

    def test_not_at_risk_when_approved(self):
        sub = KYCSubmission.objects.create(
            merchant=self.user,
            state=KYCSubmission.STATE_APPROVED,
            submitted_at=timezone.now() - timezone.timedelta(hours=48),
        )
        self.assertFalse(sub.is_at_risk)


class APIAuthTests(APITestCase):
    """Test authentication and authorization at the API layer."""

    def setUp(self):
        # Merchant A
        self.merchant_a = User.objects.create_user(username='merchant_a', password='pass123')
        UserProfile.objects.create(user=self.merchant_a, role='merchant')
        self.token_a = Token.objects.create(user=self.merchant_a)

        # Merchant B
        self.merchant_b = User.objects.create_user(username='merchant_b', password='pass123')
        UserProfile.objects.create(user=self.merchant_b, role='merchant')
        self.token_b = Token.objects.create(user=self.merchant_b)

        # Reviewer
        self.reviewer = User.objects.create_user(username='reviewer1', password='pass123')
        UserProfile.objects.create(user=self.reviewer, role='reviewer')
        self.token_reviewer = Token.objects.create(user=self.reviewer)

        # Submission belonging to merchant A
        self.submission_a = KYCSubmission.objects.create(merchant=self.merchant_a)

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_merchant_cannot_see_other_merchant_submission(self):
        """Merchant B must get 403 when accessing Merchant A's submission."""
        self._auth(self.token_b)
        response = self.client.get(f'/api/v1/merchant/submissions/{self.submission_a.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_merchant_can_see_own_submission(self):
        self._auth(self.token_a)
        response = self.client.get(f'/api/v1/merchant/submissions/{self.submission_a.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reviewer_can_see_any_submission(self):
        self._auth(self.token_reviewer)
        response = self.client.get(f'/api/v1/reviewer/submissions/{self.submission_a.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_merchant_cannot_access_reviewer_queue(self):
        self._auth(self.token_a)
        response = self.client.get('/api/v1/reviewer/queue/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get('/api/v1/merchant/submissions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class IllegalStateTransitionAPITests(APITestCase):
    """Test that illegal state transitions return 400 at the API layer."""

    def setUp(self):
        self.reviewer = User.objects.create_user(username='rev', password='pass123')
        UserProfile.objects.create(user=self.reviewer, role='reviewer')
        self.token = Token.objects.create(user=self.reviewer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.merchant = User.objects.create_user(username='merch', password='pass123')
        UserProfile.objects.create(user=self.merchant, role='merchant')

        self.submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            state=KYCSubmission.STATE_APPROVED,
        )

    def test_cannot_transition_approved_to_draft_via_api(self):
        response = self.client.post(
            f'/api/v1/reviewer/submissions/{self.submission.pk}/transition/',
            {'new_state': 'draft'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_cannot_transition_approved_to_submitted_via_api(self):
        response = self.client.post(
            f'/api/v1/reviewer/submissions/{self.submission.pk}/transition/',
            {'new_state': 'submitted'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notification_logged_on_valid_transition(self):
        self.submission.state = KYCSubmission.STATE_UNDER_REVIEW
        self.submission.save()
        response = self.client.post(
            f'/api/v1/reviewer/submissions/{self.submission.pk}/transition/',
            {'new_state': 'approved', 'note': 'All good'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            NotificationEvent.objects.filter(
                merchant=self.merchant,
                event_type='kyc_state_changed_to_approved',
            ).exists()
        )
