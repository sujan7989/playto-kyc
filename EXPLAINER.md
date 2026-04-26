# EXPLAINER.md — Playto KYC Pipeline

---

## 1. The State Machine

**Where does it live?**

`kyc/models.py` — inside the `KYCSubmission` model. It is the single source of truth. No state logic exists in views or serializers.

```python
# Legal transitions: current_state -> [allowed next states]
LEGAL_TRANSITIONS = {
    STATE_DRAFT: [STATE_SUBMITTED],
    STATE_SUBMITTED: [STATE_UNDER_REVIEW],
    STATE_UNDER_REVIEW: [STATE_APPROVED, STATE_REJECTED, STATE_MORE_INFO],
    STATE_MORE_INFO: [STATE_SUBMITTED],
    STATE_APPROVED: [],   # terminal
    STATE_REJECTED: [],   # terminal
}

def can_transition_to(self, new_state: str) -> bool:
    return new_state in self.LEGAL_TRANSITIONS.get(self.state, [])

def transition_to(self, new_state: str, reviewer=None, note: str = '') -> None:
    if not self.can_transition_to(new_state):
        allowed = self.LEGAL_TRANSITIONS.get(self.state, [])
        raise ValueError(
            f"Cannot transition from '{self.state}' to '{new_state}'. "
            f"Allowed transitions: {allowed or ['none (terminal state)']}"
        )
    # ... sets timestamps, reviewer, note, saves
```

**How is an illegal transition prevented?**

`transition_to()` raises `ValueError` if the transition is not in `LEGAL_TRANSITIONS[current_state]`. The view catches this and returns a `400` with the error message. The dict is the only place transitions are defined — adding a new state means editing one dict, not hunting through views.

---

## 2. The Upload

**How are file uploads validated?**

In `kyc/serializers.py`, `DocumentUploadSerializer.validate_file()`:

```python
def validate_file(self, file):
    # 1. Size check — reject before reading content
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

    # 3. MIME type check by reading file header bytes (not trusting client)
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
    # Try python-magic first (reads actual file bytes)
    try:
        import magic as libmagic
        return libmagic.from_buffer(header, mime=True)
    except (ImportError, Exception):
        pass
    # Fallback: check magic bytes manually
    if header[:4] == b'%PDF':
        return 'application/pdf'
    if header[:2] == b'\xff\xd8':   # JPEG SOI marker
        return 'image/jpeg'
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    # Last resort: trust extension
    ext_to_mime = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg',
                   '.jpeg': 'image/jpeg', '.png': 'image/png'}
    return ext_to_mime.get(ext, 'application/octet-stream')
```

**What happens with a 50 MB file?**

Django's `DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024` in settings rejects it at the middleware layer before it even reaches the view. If somehow it passes (e.g. chunked upload), `validate_file` catches it at the `file.size` check and returns a `400` with a human-readable message showing the actual file size.

---

## 3. The Queue

**The query powering the reviewer dashboard queue:**

```python
# kyc/views.py — ReviewerQueueView
queue_states = [KYCSubmission.STATE_SUBMITTED, KYCSubmission.STATE_UNDER_REVIEW]
submissions = KYCSubmission.objects.filter(
    state__in=queue_states
).select_related('merchant', 'assigned_reviewer').order_by('submitted_at', 'created_at')
```

**Why this way?**

- `state__in=[...]` — single indexed query, no full table scan
- `select_related('merchant', 'assigned_reviewer')` — avoids N+1 queries when serializing merchant username
- `order_by('submitted_at', 'created_at')` — oldest submitted first (FIFO queue). `created_at` is the tiebreaker for submissions that haven't been submitted yet
- SLA `is_at_risk` is a `@property` on the model — computed in Python, never stored. This means it's always accurate and never goes stale

**The metrics query:**

```python
# Average time in queue — computed in Python (not SQL) for SQLite compatibility
for sub in queue_qs:
    ref = sub.submitted_at or sub.created_at
    total_hours += (now - ref).total_seconds() / 3600

# Approval rate last 7 days
recent = KYCSubmission.objects.filter(
    reviewed_at__gte=seven_days_ago,
    state__in=[STATE_APPROVED, STATE_REJECTED],
)
approval_rate = approved_count / total_reviewed * 100
```

---

## 4. The Auth

**How does the system stop merchant A from seeing merchant B's submission?**

Two layers:

**Layer 1 — Permission class** (`kyc/permissions.py`):
```python
class IsMerchant(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.is_merchant
        )
```
This ensures only merchants can hit merchant endpoints at all.

**Layer 2 — Object-level check in the view** (`kyc/views.py`):
```python
def _get_submission(self, pk, user):
    try:
        submission = KYCSubmission.objects.get(pk=pk)
    except KYCSubmission.DoesNotExist:
        return None, error_response("Submission not found.", 404)

    # THE KEY CHECK: merchant can only access their own submission
    if hasattr(user, 'profile') and user.profile.is_merchant:
        if submission.merchant != user:
            return None, error_response(
                "You do not have permission to access this submission.",
                403,
            )
    return submission, None
```

The check is `submission.merchant != user` — a direct FK comparison. Even if merchant B guesses submission ID 1 (which belongs to merchant A), they get a `403`. Reviewers bypass this check and can see all submissions.

---

## 5. The AI Audit

**What AI got wrong and what I caught:**

When I asked AI to generate the `MerchantSubmissionDetailView._get_submission` method, it produced this:

```python
# AI-generated (BUGGY):
def _get_submission(self, pk, user):
    try:
        submission = KYCSubmission.objects.get(pk=pk)
    except KYCSubmission.DoesNotExist:
        return None, error_response("Submission not found.", 404)

    # AI called the permission class with None for request
    if not IsOwnerMerchant().has_object_permission(None, None, submission):
        pass  # handled below via manual check

    if hasattr(user, 'profile') and user.profile.is_merchant:
        if submission.merchant != user:
            return None, error_response("Forbidden", 403)
    return submission, None
```

**The bug:** `IsOwnerMerchant().has_object_permission(None, None, submission)` passes `None` as the `request` argument. Inside `has_object_permission`, the code does `request.user` — which crashes with `AttributeError: 'NoneType' object has no attribute 'user'`.

This was caught immediately when running tests — `test_merchant_can_see_own_submission` and `test_merchant_cannot_see_other_merchant_submission` both errored with that exact traceback.

**What I replaced it with:**

```python
# Fixed: removed the broken permission class call entirely,
# kept only the direct ownership check which is cleaner anyway
if hasattr(user, 'profile') and user.profile.is_merchant:
    if submission.merchant != user:
        return None, error_response(
            "You do not have permission to access this submission.",
            403,
        )
```

The AI was trying to reuse the permission class in a context it wasn't designed for (permission classes expect a real `request` object). The fix is simpler and more readable — just do the ownership check directly.
