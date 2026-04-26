import os
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers
from .models import KYCSubmission, KYCDocument, NotificationEvent, UserProfile


# ── Auth serializers ───────────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['merchant', 'reviewer'])

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def create(self, validated_data):
        role = validated_data.pop('role')
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data['email'],
        )
        UserProfile.objects.create(user=user, role=role)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


# ── Document serializer ────────────────────────────────────────────────────────

class KYCDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = KYCDocument
        fields = ['id', 'doc_type', 'original_filename', 'file_size', 'uploaded_at', 'file_url']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None


class DocumentUploadSerializer(serializers.Serializer):
    """
    Validates file uploads: type (PDF/JPG/PNG) and size (max 5 MB).
    Validation happens server-side — we never trust the client's Content-Type.
    """
    doc_type = serializers.ChoiceField(choices=[
        ('pan', 'PAN Card'),
        ('aadhaar', 'Aadhaar Card'),
        ('bank_statement', 'Bank Statement'),
    ])
    file = serializers.FileField()

    def validate_file(self, file):
        # 1. Size check
        if file.size > KYCDocument.MAX_FILE_SIZE_BYTES:
            raise serializers.ValidationError(
                f"File too large. Maximum allowed size is 5 MB. "
                f"Your file is {file.size / (1024*1024):.1f} MB."
            )

        # 2. Extension check
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in KYCDocument.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Invalid file extension '{ext}'. Allowed: PDF, JPG, PNG."
            )

        # 3. MIME type check by reading file header (not trusting client)
        file.seek(0)
        header = file.read(2048)
        file.seek(0)

        detected_mime = self._detect_mime(header, ext)
        if detected_mime not in KYCDocument.ALLOWED_MIME_TYPES:
            raise serializers.ValidationError(
                f"Invalid file type detected: '{detected_mime}'. "
                f"Only PDF, JPG, and PNG files are accepted."
            )

        return file

    def _detect_mime(self, header: bytes, ext: str) -> str:
        """
        Detect MIME type from file header bytes.
        Uses python-magic if available, otherwise falls back to magic bytes.
        """
        try:
            import magic as libmagic
            mime = libmagic.from_buffer(header, mime=True)
            return mime
        except (ImportError, Exception):
            pass

        # Fallback: check magic bytes manually
        if header[:4] == b'%PDF':
            return 'application/pdf'
        if header[:2] in (b'\xff\xd8',):  # JPEG SOI marker
            return 'image/jpeg'
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image/png'

        # Last resort: trust extension (weakest check)
        ext_to_mime = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
        }
        return ext_to_mime.get(ext, 'application/octet-stream')


# ── KYC Submission serializers ─────────────────────────────────────────────────

class KYCSubmissionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    merchant_username = serializers.CharField(source='merchant.username', read_only=True)
    is_at_risk = serializers.SerializerMethodField()
    time_in_queue_hours = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = [
            'id', 'merchant_username', 'state', 'business_name',
            'submitted_at', 'created_at', 'is_at_risk', 'time_in_queue_hours',
        ]

    def get_is_at_risk(self, obj):
        return obj.is_at_risk

    def get_time_in_queue_hours(self, obj):
        if obj.state not in (KYCSubmission.STATE_SUBMITTED, KYCSubmission.STATE_UNDER_REVIEW):
            return None
        ref = obj.submitted_at or obj.created_at
        return round((timezone.now() - ref).total_seconds() / 3600, 1)


class KYCSubmissionDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail views."""
    merchant_username = serializers.CharField(source='merchant.username', read_only=True)
    reviewer_username = serializers.CharField(
        source='assigned_reviewer.username', read_only=True, default=None
    )
    documents = KYCDocumentSerializer(many=True, read_only=True)
    is_at_risk = serializers.SerializerMethodField()
    time_in_queue_hours = serializers.SerializerMethodField()
    allowed_transitions = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = [
            'id', 'merchant_username', 'reviewer_username', 'state',
            'full_name', 'email', 'phone',
            'business_name', 'business_type', 'expected_monthly_volume',
            'reviewer_note', 'documents',
            'created_at', 'updated_at', 'submitted_at', 'reviewed_at',
            'is_at_risk', 'time_in_queue_hours', 'allowed_transitions',
        ]

    def get_is_at_risk(self, obj):
        return obj.is_at_risk

    def get_time_in_queue_hours(self, obj):
        if obj.state not in (KYCSubmission.STATE_SUBMITTED, KYCSubmission.STATE_UNDER_REVIEW):
            return None
        ref = obj.submitted_at or obj.created_at
        return round((timezone.now() - ref).total_seconds() / 3600, 1)

    def get_allowed_transitions(self, obj):
        return KYCSubmission.LEGAL_TRANSITIONS.get(obj.state, [])


class KYCSubmissionUpdateSerializer(serializers.ModelSerializer):
    """For merchants to update their draft submission."""
    class Meta:
        model = KYCSubmission
        fields = [
            'full_name', 'email', 'phone',
            'business_name', 'business_type', 'expected_monthly_volume',
        ]


class StateTransitionSerializer(serializers.Serializer):
    """Used by reviewers to change submission state."""
    new_state = serializers.ChoiceField(choices=KYCSubmission.STATE_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True, default='')


# ── Notification serializer ────────────────────────────────────────────────────

class NotificationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ['id', 'event_type', 'timestamp', 'payload']


# ── Dashboard metrics serializer ───────────────────────────────────────────────

class DashboardMetricsSerializer(serializers.Serializer):
    submissions_in_queue = serializers.IntegerField()
    average_time_in_queue_hours = serializers.FloatField()
    approval_rate_last_7_days = serializers.FloatField()
    at_risk_count = serializers.IntegerField()
