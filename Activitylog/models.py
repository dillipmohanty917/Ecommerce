from django.db import models

from b2b2 import settings



class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='from_user_activity_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255,default="")
    details = models.TextField()
    order = models.ForeignKey('Ordermanagement.Order', on_delete=models.SET_NULL, null=True, blank=True)
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='to_user_activity_logs')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.user.username if self.user else 'System'}: {self.action}"

    @classmethod
    def log_activity(cls, user, action, details, order=None, to_user=None):
        """
        Log an activity.

        :param user: The user performing the action.
        :param action: The action being performed.
        :param details: Additional details about the action.
        :param order: The associated order (if applicable).
        """
        cls.objects.create(user=user, action=action, details=details, order=order, to_user=to_user)