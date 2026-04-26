# Playto KYC Pipeline

Cross-border payment KYC onboarding system for Playto Pay. Merchants submit KYC, reviewers approve/reject through a state-machine-enforced pipeline.

## Stack
- **Backend**: Django 5 + Django REST Framework + SQLite
- **Frontend**: React + Vite + Tailwind CSS
- **Auth**: Token-based (DRF TokenAuthentication)

---

## Quick Start (Local)

### 1. Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Copy env
cp .env.example .env

# Run migrations
python manage.py migrate

# Seed test data
python manage.py seed

# Start server
python manage.py runserver
```

Backend runs at: http://localhost:8000

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:3000

---

## Docker (One Command)

```bash
docker-compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

---

## Test Credentials (after seed)

| Role     | Username         | Password     |
|----------|-----------------|--------------|
| Reviewer | reviewer1        | reviewer123  |
| Merchant | merchant_draft   | merchant123  |
| Merchant | merchant_review  | merchant123  |

---

## Run Tests

```bash
python manage.py test kyc --verbosity=2
```

20 tests covering:
- State machine (legal + illegal transitions)
- SLA at_risk computation
- Auth isolation (merchant A cannot see merchant B)
- API-layer state enforcement
- Notification logging

---

## API Reference

All endpoints under `/api/v1/`

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register/` | Register merchant or reviewer |
| POST | `/auth/login/` | Login, returns token |
| GET  | `/auth/me/` | Current user info |

### Merchant
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/merchant/submissions/` | List or create submissions |
| GET/PATCH | `/merchant/submissions/:id/` | View or update draft |
| POST | `/merchant/submissions/:id/submit/` | Submit for review |
| POST | `/merchant/submissions/:id/documents/` | Upload document |
| GET  | `/merchant/notifications/` | Notification events |

### Reviewer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reviewer/queue/` | Queue (submitted + under_review), oldest first |
| GET | `/reviewer/submissions/` | All submissions (filterable by state) |
| GET | `/reviewer/submissions/:id/` | Full submission detail |
| POST | `/reviewer/submissions/:id/transition/` | Change state |
| GET | `/reviewer/dashboard/metrics/` | Dashboard metrics |

---

## State Machine

```
draft → submitted → under_review → approved (terminal)
                                 → rejected (terminal)
                                 → more_info_requested → submitted
```

Illegal transitions return `400` with a clear error message.

---

## File Upload Rules
- Accepted: PDF, JPG, PNG
- Max size: 5 MB
- Validated server-side by reading file header bytes (not trusting client Content-Type)
- Rejected files return `400` with specific error message

---

## SLA Tracking
- Submissions in `submitted` or `under_review` for > 24 hours are flagged `at_risk`
- Computed dynamically — never stored as a stale flag
- Visible in reviewer dashboard queue and metrics
