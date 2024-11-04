from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages

from Usermanagement.utils import marketing_admin_required, active_admin_required
from Usermanagement.api.utils import send_push_notification, upload_image_to_s3
from .models import ActivityLog




@active_admin_required
def send_notification(request):
    if request.method == 'POST':
        notification = request.POST.get('message', '').strip()
        image = request.FILES.get('image')
        image_url = None
        
        if not notification:
            messages.error(request, "Notification message cannot be empty.")
            return redirect('send_notification')
        
        if image:
            if image.content_type not in ['image/jpeg', 'image/png']:
                messages.error(request, "Invalid file type. Only JPEG and PNG files are allowed.")
                return redirect('send_notification')
            if upload_image_to_s3(image.name, image):
                image_url = f"{settings.S3_LINK}notification/{image.name}"
        if notification:
            send_push_notification(notification, image_url)
            ActivityLog.log_activity(request.user, "sent", notification)
            messages.success(request, "Notification Sent")
            return redirect('send_notification')
    
    activity_logs = ActivityLog.objects.filter(action="sent").order_by('-timestamp')
    return render(request, 'send_notification.html', {'activity_logs': activity_logs})



@marketing_admin_required
def marketing_send_notification(request):
    if request.method == 'POST':
        notification = request.POST.get('message', '').strip()
        image = request.FILES.get('image')
        image_url = None
        
        if not notification:
            messages.error(request, "Notification message cannot be empty.")
            return redirect('marketing_send_notification')
        
        if image:
            if image.content_type not in ['image/jpeg', 'image/png']:
                messages.error(request, "Invalid file type. Only JPEG and PNG files are allowed.")
                return redirect('marketing_send_notification')
            if upload_image_to_s3(image.name, image):
                image_url = f"{settings.S3_LINK}notification/{image.name}"
        if notification:
            send_push_notification(notification, image_url)
            ActivityLog.log_activity(request.user, "sent", notification)
            messages.success(request, "Notification Sent")
            return redirect('marketing_send_notification')
    
    activity_logs = ActivityLog.objects.filter(action="sent").order_by('-timestamp')
    return render(request, 'marketing_send_notification.html', {'activity_logs': activity_logs})