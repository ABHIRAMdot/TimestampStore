from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth import logout


class UserStatusCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check for authenticated users
        if request.user.is_authenticated:
            user = request.user

            # If user is blocked or inactive (force logout)
            if getattr(user, "is_blocked", False) or not getattr(
                user, "is_active", True
            ):
                logout(request)

                if getattr(user, "is_blocked", False):
                    messages.error(request, "Your account has been blocked by admin.")
                else:
                    messages.error(request, "Your account is inactive.")

                return redirect("login")

        return self.get_response(request)
