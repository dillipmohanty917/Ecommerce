# myproject/apscheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from Productmanagement.management.commands.cronjob import Command
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(Command().handle, 'interval', minutes=10)
    # scheduler.add_job(Command().handle_reports, 'interval', minutes=1)
    scheduler.add_job(Command().handle_dailysalesreports, CronTrigger(hour=22, minute=5))
    now = datetime.now()
    next_month = now.replace(day=1) + timedelta(days=31)
    next_month = next_month.replace(day=1)
    scheduler.add_job(Command().handle_monthlysalesreports, CronTrigger(year=next_month.year, month=next_month.month, day=next_month.day, hour=23, minute=59))
    scheduler.start()
