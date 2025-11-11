from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import os
import sqlite3
import code
from admin import DATABASE_PATH, jobstores

scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

jobs = scheduler.get_jobs()
for job in jobs:
  print("Job ID: {}, Next Run Time: {}".format(job.id, job.next_run_time))

code.interact(local=globals())