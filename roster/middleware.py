from django.conf import settings


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response['Content-Security-Policy'] = "frame-ancestors 'self' https://* * ;"

        return response


class AccessKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        access_key = request.COOKIES.get('AccessKey')
        if access_key and access_key != settings.ACCESS_KEY:
            print(">>>> CLEARING ACCESS KEY")
            response.set_cookie('AccessKey', '', samesite='None', secure=True)

        return response
