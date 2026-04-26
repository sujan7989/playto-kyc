"""
Seed script: creates 2 merchants and 1 reviewer with test KYC data.

Usage:
    python manage.py seed
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from rest_framework.authtoken.models import Token

from kyc.models import UserProfile, KYCSubmission, NotificationEvent


class Command(BaseCommand):
    help = 'Seed the database with test merchants and reviewer'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # ── Reviewer ──────────────────────────────────────────────────────────
        reviewer, created = User.objects.get_or_create(
            username='reviewer1',
            defaults={'email': 'reviewer@playto.so'}
        )
        if created:
            reviewer.set_password('reviewer123')
            reviewer.save()
            UserProfile.objects.create(user=reviewer, role='reviewer')
        token_r, _ = Token.objects.get_or_create(user=reviewer)
        self.stdout.write(f'  Reviewer: reviewer1 / reviewer123  (token: {token_r.key})')

        # ── Merchant 1: draft submission ──────────────────────────────────────
        m1, created = User.objects.get_or_create(
            username='merchant_draft',
            defaults={'email': 'draft@example.com'}
        )
        if created:
            m1.set_password('merchant123')
            m1.save()
            UserProfile.objects.create(user=m1, role='merchant')
        token_m1, _ = Token.objects.get_or_create(user=m1)

        sub1, _ = KYCSubmission.objects.get_or_create(
            merchant=m1,
            defaults={
                'state': KYCSubmission.STATE_DRAFT,
                'full_name': 'Rahul Sharma',
                'email': 'rahul@example.com',
                'phone': '+91-9876543210',
                'business_name': 'Rahul Designs',
                'business_type': 'freelancer',
                'expected_monthly_volume': 2000.00,
            }
        )
        self.stdout.write(
            f'  Merchant 1: merchant_draft / merchant123  '
            f'(token: {token_m1.key}) — KYC #{sub1.pk} in DRAFT'
        )

        # ── Merchant 2: under_review submission (25h old = at_risk) ──────────
        m2, created = User.objects.get_or_create(
            username='merchant_review',
            defaults={'email': 'review@example.com'}
        )
        if created:
            m2.set_password('merchant123')
            m2.save()
            UserProfile.objects.create(user=m2, role='merchant')
        token_m2, _ = Token.objects.get_or_create(user=m2)

        sub2, _ = KYCSubmission.objects.get_or_create(
            merchant=m2,
            defaults={
                'state': KYCSubmission.STATE_UNDER_REVIEW,
                'full_name': 'Priya Patel',
                'email': 'priya@example.com',
                'phone': '+91-9123456789',
                'business_name': 'Patel Digital Agency',
                'business_type': 'agency',
                'expected_monthly_volume': 15000.00,
                'submitted_at': timezone.now() - timedelta(hours=25),  # at_risk!
                'assigned_reviewer': reviewer,
            }
        )
        self.stdout.write(
            f'  Merchant 2: merchant_review / merchant123  '
            f'(token: {token_m2.key}) — KYC #{sub2.pk} in UNDER_REVIEW (at_risk=True)'
        )

        # Log a notification for merchant 2
        NotificationEvent.objects.get_or_create(
            merchant=m2,
            event_type='kyc_state_changed_to_under_review',
            defaults={
                'payload': {
                    'submission_id': sub2.pk,
                    'new_state': 'under_review',
                    'reviewer': reviewer.username,
                }
            }
        )

        self.stdout.write(self.style.SUCCESS('\nSeed complete! Login credentials:'))
        self.stdout.write('  Reviewer:   reviewer1 / reviewer123')
        self.stdout.write('  Merchant 1: merchant_draft / merchant123  (draft KYC)')
        self.stdout.write('  Merchant 2: merchant_review / merchant123  (under_review KYC)')
