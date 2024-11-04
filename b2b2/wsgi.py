"""
WSGI config for b2b2 project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
# import sys
# import threading
# import time
# import requests
# import json
from django.core.wsgi import get_wsgi_application

# import logging
# from concurrent.futures import ThreadPoolExecutor

# from Productmanagement.views import get_medica_products

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'b2b2.settings')

application = get_wsgi_application()




# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# def schedule_task():
#     def job():
#         logger.info('Scheduler started.')
#         while True:
#             try:
#                 executor = ThreadPoolExecutor(max_workers=2)
#                 executor.submit(get_medica_products)
                
#                 time.sleep(300)
#             except Exception as e:
#                 logger.error('An error occurred: %s', str(e))
#                 time.sleep(300)

#     threading.Thread(target=job, daemon=True).start()

# schedule_task()