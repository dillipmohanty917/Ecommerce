# global_tags.py

from django import template
from b2b2.settings import backendTechAdmin
# from urllib.parse import urlencode
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

register = template.Library()

@register.simple_tag(takes_context=True)
def get_query_params(context,**params):
    request_get = context['request'].GET.dict()
    all_params = {}
    all_params.update(request_get)
    all_params.update(params)
    all_params.update(context.get('default_pagination_params', {}))
    return '?' + urlencode(all_params)


@register.simple_tag
def get_backend_tech_admin_mobile_no():
    return backendTechAdmin

