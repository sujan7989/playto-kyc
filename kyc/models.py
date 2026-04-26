from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_MERCHANT = 'merchant'
    ROLE_REVIEWER = 'reviewer'
    ROLE_CHOICES = [
        (ROLE_MERCHANT, 'Merchant'),
        (ROLE_REVIEWER, 'Reviewer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MERCHANT)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_merchant(self):
        return self.role == self.ROLE_MERCHANT

    @property
    def is_reviewer(self):
        return self.role == self.ROLE_REVIEWER


class KYCSubmission(models.Model):
    # ── State machine ──────────────────────────────────────────────────────────
    STATE_DRAFT = 'draft'
    STATE_SUBMITTED = 'submitted'
    STATE_UNDER_REVIEW = 'under_review'
    STATE_APPROVED = 'approved'
    STATE_REJECTED = 'rejected'
    STATE_MORE_INFO = 'more_info_requested'

    STATE_CHOICES = [
        (STATE_DRAFT, 'Draft'),
        (STATE_SUBMITTED, 'Submitted'),
        (STATE_UNDER_REVIEW, 'Under Review'),
        (STATE_APPROVED, 'Approved'),
        (STATE_REJECTED, 'Rejected'),
        (STATE_MORE_INFO, 'More Info Requested'),
    ]

    # Legal transitions: current_state -> [allowed next states]
    LEGAL_TRANSITIONS = {
        STATE_DRAFT: [STATE_SUBMITTED],
        STATE_SUBMITTED: [STATE_UNDER_REVIEW],
        STATE_UNDER_REVIEW: [STATE_APPROVED, STATE_REJECTED, STATE_MORE_INFO],
        STATE_MORE_INFO: [STATE_SUBMITTED],
        STATE_APPROVED: [],   # terminal
        STATE_REJECTED: [],   # terminal
    }

    # ── Business type choices ──────────────────────────────────────────────────
    BUSINESS_TYPE_CHOICES = [
        ('freelancer', 'Freelancer'),
        ('agency', 'Agency'),
        ('ecommerce', 'E-Commerce'),
        ('saas', 'SaaS'),
        ('other', 'Other'),
    ]

    # ── Core fields ───────────────────────────────────────────────────────────
    merchant = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='kyc_submissions'
    )
    state = models.CharField(
        max_length=30, choices=STATE_CHOICES, default=STATE_DRAFT, db_index=True
    )
    assigned_reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_submissions'
    )

    # Personal details
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Business details
    business_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(
        max_length=50, choices=BUSINESS_TYPE_CHOICES, blank=True
    )
    expected_monthly_volume = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Expected monthly volume in USD'
    )

    # Reviewer notes
    reviewer_note = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['submitted_at', 'created_at']

    def __str__(self):
        return f"KYC#{self.pk} - {self.merchant.username} [{self.state}]"

    # ── State machine enforcement ──────────────────────────────────────────────
    def can_transition_to(self, new_state: str) -> bool:
        """Return True if the transition from current state to new_state is legal."""
        return new_state in self.LEGAL_TRANSITIONS.get(self.state, [])

    def transition_to(self, new_state: str, reviewer=None, note: str = '') -> None:
        """
        Perform a state transition. Raises ValueError on illegal transitions.
        This is the single source of truth for state changes.
        """
        if not self.can_transition_to(new_state):
            allowed = self.LEGAL_TRANSITIONS.get(self.state, [])
            raise ValueError(
                f"Cannot transition from '{self.state}' to '{new_state}'. "
                f"Allowed transitions: {allowed or ['none (terminal state)']}"
            )

        now = timezone.now()
        self.state = new_state

        if new_state == self.STATE_SUBMITTED:
            self.submitted_at = now

        if new_state in (self.STATE_APPROVED, self.STATE_REJECTED, self.STATE_MORE_INFO):
            self.reviewed_at = now
            if reviewer:
                self.assigned_reviewer = reviewer
            if note:
                self.reviewer_note = note

        self.save()

    @property
    def is_at_risk(self) -> bool:
        """
        Dynamically computed — never stored. A submission is at_risk if it has
        been in the queue (submitted or under_review) for more than 24 hours.
        """
        from django.conf import settings
        threshold_hours = getattr(settings, 'KYC_SLA_THRESHOLD_HOURS', 24)

        if self.state not in (self.STATE_SUBMITTED, self.STATE_UNDER_REVIEW):
            return False

        reference_time = self.submitted_at or self.created_at
        age_hours = (timezone.now() - reference_time).total_seconds() / 3600
        return age_hours > threshold_hours


def document_upload_path(instance, filename):
    """Store documents under media/kyc_docs/<submission_id>/<filename>"""
    return f"kyc_docs/{instance.submission.pk}/{filename}"


class KYCDocument(models.Model):
    DOC_PAN = 'pan'
    DOC_AADHAAR = 'aadhaar'
    DOC_BANK_STATEMENT = 'bank_statement'
    DOC_TYPE_CHOICES = [
        (DOC_PAN, 'PAN Card'),
        (DOC_AADHAAR, 'Aadhaar Card'),
        (DOC_BANK_STATEMENT, 'Bank Statement'),
    ]

    ALLOWED_MIME_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

    submission = models.ForeignKey(
        KYCSubmission, on_delete=models.CASCADE, related_name='documents'
    )
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text='File size in bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('submission', 'doc_type')

    def __str__(self):
        return f"{self.doc_type} for KYC#{self.submission.pk}"


class NotificationEvent(models.Model):
    merchant = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notification_events'
    )
    event_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} for {self.merchant.username} at {self.timestamp}"
