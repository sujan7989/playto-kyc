from rest_framework.permissions import BasePermission


class IsMerchant(BasePermission):
    """Allow access only to users with the merchant role."""
    message = "Only merchants can perform this action."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.is_merchant
        )


class IsReviewer(BasePermission):
    """Allow access only to users with the reviewer role."""
    message = "Only reviewers can perform this action."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.is_reviewer
        )


class IsOwnerMerchant(BasePermission):
    """
    Object-level permission: a merchant can only access their own submission.
    This is the check that prevents merchant A from seeing merchant B's data.
    """
    message = "You do not have permission to access this submission."

    def has_object_permission(self, request, view, obj):
        # Reviewers can see everything
        if hasattr(request.user, 'profile') and request.user.profile.is_reviewer:
            return True
        # Merchants can only see their own
        return obj.merchant == request.user
