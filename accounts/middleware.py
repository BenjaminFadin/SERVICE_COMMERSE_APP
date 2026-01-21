from django.utils import translation

class UserLanguageMiddleware:
    """
    If user is authenticated and has profile.language -> activate it.
    Else fallback to session/cookie/Accept-Language handled by LocaleMiddleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = None

        if getattr(request, "user", None) and request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile and profile.language:
                lang = profile.language

        if lang:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang

        response = self.get_response(request)

        if lang:
            translation.deactivate()

        return response
