from django.contrib.auth.backends import ModelBackend
from .models import User
from django.core.exceptions import MultipleObjectsReturned


class CustomAuthentication(ModelBackend):
    """
    Phone, Email, and Username Authentication Backend

    Allows a user to sign in using a phone number, email, or username with a password.
    """
    def authenticate(self, request, **kwargs):
        """ Authenticate a user based on phone/email/username as the user name. """
        username = kwargs['username']
        password = kwargs['password']
        try:
            if '@' in username:
                user = User.objects.get(email=username)
            # elif User.objects.filter(username=username).exists():
            #     user = User.objects.get(username=username)
            else:
                if len(username) == 10:
                    username = "91" + username
                user = User.objects.get(username=username)

            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        except MultipleObjectsReturned:
            return None
    
    """ get user """
    def get_user(self, user_id):
        """ Get a User object from the user_id. """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
