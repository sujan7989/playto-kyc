from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Return consistent error shapes:
    { "error": "...", "detail": "..." }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            'error': True,
            'status_code': response.status_code,
        }

        if isinstance(response.data, dict):
            if 'detail' in response.data:
                error_data['detail'] = str(response.data['detail'])
            else:
                error_data['detail'] = response.data
        elif isinstance(response.data, list):
            error_data['detail'] = response.data
        else:
            error_data['detail'] = str(response.data)

        response.data = error_data

    return response
