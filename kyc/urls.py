from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/me/', views.MeView.as_view(), name='me'),

    # Merchant: KYC submissions
    path('merchant/submissions/', views.MerchantSubmissionListCreateView.as_view(), name='merchant-submissions'),
    path('merchant/submissions/<int:pk>/', views.MerchantSubmissionDetailView.as_view(), name='merchant-submission-detail'),
    path('merchant/submissions/<int:pk>/submit/', views.MerchantSubmitView.as_view(), name='merchant-submit'),
    path('merchant/submissions/<int:pk>/documents/', views.DocumentUploadView.as_view(), name='document-upload'),
    path('merchant/notifications/', views.MerchantNotificationsView.as_view(), name='merchant-notifications'),

    # Reviewer
    path('reviewer/queue/', views.ReviewerQueueView.as_view(), name='reviewer-queue'),
    path('reviewer/submissions/', views.ReviewerAllSubmissionsView.as_view(), name='reviewer-submissions'),
    path('reviewer/submissions/<int:pk>/', views.ReviewerSubmissionDetailView.as_view(), name='reviewer-submission-detail'),
    path('reviewer/submissions/<int:pk>/transition/', views.ReviewerTransitionView.as_view(), name='reviewer-transition'),
    path('reviewer/dashboard/metrics/', views.ReviewerDashboardMetricsView.as_view(), name='reviewer-metrics'),
]
