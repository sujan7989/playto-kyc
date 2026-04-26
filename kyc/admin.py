from django.contrib import admin
from .models import UserProfile, KYCSubmission, KYCDocument, NotificationEvent


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']
    list_filter = ['role']


@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'state', 'business_name', 'submitted_at', 'created_at']
    list_filter = ['state']
    search_fields = ['merchant__username', 'business_name']


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'submission', 'doc_type', 'original_filename', 'file_size', 'uploaded_at']


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'event_type', 'timestamp']
    list_filter = ['event_type']
