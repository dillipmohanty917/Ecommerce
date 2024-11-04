from Activitylog.models import ActivityLog


def validate_file_type(file):
    if str(file).lower().endswith('.csv') or str(file).lower().endswith('.xlsx') or str(file).lower().endswith('.xls'):
        return True
    else:
        return False
    
    
def extract_form_data(request, *fields):
    """
    Helper function to extract form data from a POST request.

    Parameters:
    - request: The HTTP request object.
    - *fields: Variable number of field names to extract.
    Returns:
    - A dictionary containing the extracted form data.
    """
    form_data = {}
    if request.method == 'POST':
        for field in fields:
            form_data[field] = request.POST.get(field,"")
    return form_data

def log_activity(request, status,order_instance):
    ActivityLog.log_activity(
        user=request.user,
        order=order_instance,
        action=order_instance.order_status,
        details=f"Order {status} by the distributor: {order_instance.distributor.name}" if request.user.is_distributor else f"Order {status} by the Admin: {request.user.username}"
    )