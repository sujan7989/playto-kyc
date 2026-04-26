from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KYCSubmission, KYCDocument, NotificationEvent, UserProfile
from .permissions import IsMerchant, IsReviewer, IsOwnerMerchant
from .serializers import (
    RegisterSerializer, LoginSerializer,
    KYCSubmissionListSerializer, KYCSubmissionDetailSerializer,
    KYCSubmissionUpdateSerializer, StateTransitionSerializer,
    DocumentUploadSerializer, NotificationEventSerializer,
    DashboardMetricsSerializer,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def log_notification(merchant: User, event_type: str, payload: dict):
    """Record a notification event. Does not send emails — just logs."""
    NotificationEvent.objects.create(
        merchant=merchant,
        event_type=event_type,
        payload=payload,
    )


def error_response(message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
    return Response(
        {'error': True, 'status_code': status_code, 'detail': message},
        status=status_code,
    )


# ── Auth views ─────────────────────────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': True, 'status_code': 400, 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'role': user.profile.role,
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': True, 'status_code': 400, 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if not user:
            return error_response("Invalid credentials.", status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'role': user.profile.role,
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'user_id': request.user.pk,
            'username': request.user.username,
            'email': request.user.email,
            'role': request.user.profile.role,
        })


# ── Merchant: KYC submission CRUD ─────────────────────────────────────────────

class MerchantSubmissionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def get(self, request):
        """List the current merchant's own submissions."""
        submissions = KYCSubmission.objects.filter(merchant=request.user)
        serializer = KYCSubmissionListSerializer(
            submissions, many=True, context={'request': request}
        )
        return Response(serializer.data)

    def post(self, request):
        """Create a new KYC submission in draft state."""
        submission = KYCSubmission.objects.create(merchant=request.user)
        serializer = KYCSubmissionDetailSerializer(
            submission, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MerchantSubmissionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def _get_submission(self, pk, user):
        try:
            submission = KYCSubmission.objects.get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return None, error_response("Submission not found.", status.HTTP_404_NOT_FOUND)

        # Merchants can only see their own submissions — this is the key auth check
        if hasattr(user, 'profile') and user.profile.is_merchant:
            if submission.merchant != user:
                return None, error_response(
                    "You do not have permission to access this submission.",
                    status.HTTP_403_FORBIDDEN,
                )
        return submission, None

    def get(self, request, pk):
        submission, err = self._get_submission(pk, request.user)
        if err:
            return err
        serializer = KYCSubmissionDetailSerializer(
            submission, context={'request': request}
        )
        return Response(serializer.data)

    def patch(self, request, pk):
        """Merchants can update their draft or more_info_requested submissions."""
        submission, err = self._get_submission(pk, request.user)
        if err:
            return err

        if submission.state not in (
            KYCSubmission.STATE_DRAFT, KYCSubmission.STATE_MORE_INFO
        ):
            return error_response(
                f"Cannot edit a submission in '{submission.state}' state. "
                "Only draft or more_info_requested submissions can be edited."
            )

        serializer = KYCSubmissionUpdateSerializer(
            submission, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(
                {'error': True, 'status_code': 400, 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response(
            KYCSubmissionDetailSerializer(submission, context={'request': request}).data
        )


class MerchantSubmitView(APIView):
    """Merchant submits their KYC for review (draft -> submitted)."""
    permission_classes = [IsAuthenticated, IsMerchant]

    def post(self, request, pk):
        try:
            submission = KYCSubmission.objects.get(pk=pk, merchant=request.user)
        except KYCSubmission.DoesNotExist:
            return error_response("Submission not found.", status.HTTP_404_NOT_FOUND)

        try:
            submission.transition_to(KYCSubmission.STATE_SUBMITTED)
        except ValueError as e:
            return error_response(str(e))

        log_notification(
            merchant=request.user,
            event_type='kyc_submitted',
            payload={
                'submission_id': submission.pk,
                'state': submission.state,
                'submitted_at': submission.submitted_at.isoformat(),
            },
        )

        return Response(
            KYCSubmissionDetailSerializer(submission, context={'request': request}).data
        )


# ── Document upload ────────────────────────────────────────────────────────────

class DocumentUploadView(APIView):
    """
    Upload a KYC document. Validates file type and size server-side.
    Only allowed when submission is in draft or more_info_requested state.
    """
    permission_classes = [IsAuthenticated, IsMerchant]

    def post(self, request, pk):
        try:
            submission = KYCSubmission.objects.get(pk=pk, merchant=request.user)
        except KYCSubmission.DoesNotExist:
            return error_response("Submission not found.", status.HTTP_404_NOT_FOUND)

        if submission.state not in (
            KYCSubmission.STATE_DRAFT, KYCSubmission.STATE_MORE_INFO
        ):
            return error_response(
                f"Cannot upload documents for a submission in '{submission.state}' state."
            )

        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': True, 'status_code': 400, 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file = serializer.validated_data['file']
        doc_type = serializer.validated_data['doc_type']

        # Replace existing document of same type
        KYCDocument.objects.filter(submission=submission, doc_type=doc_type).delete()

        doc = KYCDocument.objects.create(
            submission=submission,
            doc_type=doc_type,
            file=file,
            original_filename=file.name,
            file_size=file.size,
        )

        from .serializers import KYCDocumentSerializer
        return Response(
            KYCDocumentSerializer(doc, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


# ── Reviewer views ─────────────────────────────────────────────────────────────

class ReviewerQueueView(APIView):
    """
    Reviewer sees all submissions in the queue (submitted + under_review),
    oldest first. SLA flag is computed dynamically.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        queue_states = [KYCSubmission.STATE_SUBMITTED, KYCSubmission.STATE_UNDER_REVIEW]
        submissions = KYCSubmission.objects.filter(
            state__in=queue_states
        ).select_related('merchant', 'assigned_reviewer').order_by('submitted_at', 'created_at')

        serializer = KYCSubmissionListSerializer(
            submissions, many=True, context={'request': request}
        )
        return Response(serializer.data)


class ReviewerAllSubmissionsView(APIView):
    """Reviewer can see all submissions with optional state filter."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        qs = KYCSubmission.objects.select_related('merchant', 'assigned_reviewer').all()
        state = request.query_params.get('state')
        if state:
            qs = qs.filter(state=state)
        serializer = KYCSubmissionListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class ReviewerSubmissionDetailView(APIView):
    """Reviewer views full details of any submission."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request, pk):
        try:
            submission = KYCSubmission.objects.select_related(
                'merchant', 'assigned_reviewer'
            ).prefetch_related('documents').get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return error_response("Submission not found.", status.HTTP_404_NOT_FOUND)

        serializer = KYCSubmissionDetailSerializer(
            submission, context={'request': request}
        )
        return Response(serializer.data)


class ReviewerTransitionView(APIView):
    """
    Reviewer changes the state of a submission.
    Enforces the state machine — illegal transitions return 400.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, pk):
        try:
            submission = KYCSubmission.objects.get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return error_response("Submission not found.", status.HTTP_404_NOT_FOUND)

        serializer = StateTransitionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': True, 'status_code': 400, 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_state = serializer.validated_data['new_state']
        note = serializer.validated_data.get('note', '')

        # Reviewer must first move to under_review before approving/rejecting
        try:
            submission.transition_to(new_state, reviewer=request.user, note=note)
        except ValueError as e:
            return error_response(str(e))

        log_notification(
            merchant=submission.merchant,
            event_type=f'kyc_state_changed_to_{new_state}',
            payload={
                'submission_id': submission.pk,
                'new_state': new_state,
                'reviewer': request.user.username,
                'note': note,
                'timestamp': timezone.now().isoformat(),
            },
        )

        return Response(
            KYCSubmissionDetailSerializer(submission, context={'request': request}).data
        )


class ReviewerDashboardMetricsView(APIView):
    """
    Dashboard metrics:
    - submissions in queue
    - average time in queue (hours)
    - approval rate over last 7 days
    - at-risk count
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        queue_states = [KYCSubmission.STATE_SUBMITTED, KYCSubmission.STATE_UNDER_REVIEW]
        now = timezone.now()
        threshold = now - timedelta(hours=24)
        seven_days_ago = now - timedelta(days=7)

        # Queue submissions
        queue_qs = KYCSubmission.objects.filter(state__in=queue_states)
        submissions_in_queue = queue_qs.count()

        # Average time in queue (hours) — computed in Python for SQLite compatibility
        total_hours = 0.0
        count = 0
        for sub in queue_qs:
            ref = sub.submitted_at or sub.created_at
            if ref:
                total_hours += (now - ref).total_seconds() / 3600
                count += 1
        avg_time = round(total_hours / count, 2) if count > 0 else 0.0

        # At-risk count: in queue AND older than 24h
        at_risk_count = sum(1 for sub in queue_qs if sub.is_at_risk)

        # Approval rate last 7 days
        recent = KYCSubmission.objects.filter(
            reviewed_at__gte=seven_days_ago,
            state__in=[KYCSubmission.STATE_APPROVED, KYCSubmission.STATE_REJECTED],
        )
        total_reviewed = recent.count()
        approved_count = recent.filter(state=KYCSubmission.STATE_APPROVED).count()
        approval_rate = round(
            (approved_count / total_reviewed * 100) if total_reviewed > 0 else 0.0, 1
        )

        return Response({
            'submissions_in_queue': submissions_in_queue,
            'average_time_in_queue_hours': avg_time,
            'approval_rate_last_7_days': approval_rate,
            'at_risk_count': at_risk_count,
        })


# ── Notifications ──────────────────────────────────────────────────────────────

class MerchantNotificationsView(APIView):
    """Merchant sees their own notification events."""
    permission_classes = [IsAuthenticated, IsMerchant]

    def get(self, request):
        events = NotificationEvent.objects.filter(merchant=request.user)[:50]
        serializer = NotificationEventSerializer(events, many=True)
        return Response(serializer.data)
