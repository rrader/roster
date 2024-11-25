from django.conf import settings


class MoodleLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # if not redirecting to moodle, clear the cookie
        if not response.has_header('Location'):
            response.set_cookie('MoodleSession', '', domain=f'.{settings.BASE_DOMAIN}')

        return response


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response['Content-Security-Policy'] = "frame-ancestors 'self' https://* * ;"

        return response
