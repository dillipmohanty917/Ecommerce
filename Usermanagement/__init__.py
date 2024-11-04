from __future__ import unicode_literals
from django.conf import settings
from django.core.paginator import InvalidPage, Paginator
from django.http import Http404
from django.core.paginator import InvalidPage, Paginator,EmptyPage, PageNotAnInteger



def get_paginator_items(items, paginate_by, page_number):
    if not page_number:
        page_number = 1
    paginator = Paginator(items, paginate_by)
    try:
        page_number = int(page_number)
    except ValueError:
        raise Http404('Page can not be converted to an int.')

    try:
        items = paginator.page(page_number)
    except InvalidPage as err:
        raise Http404('Invalid page (%(page_number)s): %(message)s' % {
            'page_number': page_number, 'message': str(err)})
    return items

def paginate_items(request, queryset,items_per_page=10):
    paginator = Paginator(queryset, items_per_page)
    page = request.GET.get('page')

    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)

    return items