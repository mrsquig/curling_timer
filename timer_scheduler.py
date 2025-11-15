from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore
import requests
from datetime import datetime, timedelta
import logging
import os
import sqlite3
from admin import DATABASE_PATH, STYES_PATH, jobstores

logging.basicConfig()
logger = logging.getLogger('scheduler')
logger.setLevel(logging.INFO)

jobstores["memory"] = MemoryJobStore()
scheduler = BlockingScheduler(jobstores=jobstores)

def start_timer(profile):
  game_type = requests.get('http://localhost:5000/config?key=game_type').json().get('game_type', 'league')
  if game_type == "bonspiel":
    logger.debug("Bonspiel detected. Skipping league profile load.")
    return

  logger.info("Starting timer with profile: {:s}".format(profile))
  requests.get('http://localhost:5000/load_profile?name={}'.format(profile))
  requests.get('http://localhost:5000/reset')
  requests.get('http://localhost:5000/start')

def start_bonspiel(job_id, time_to_chime, time_per_end, stones_per_end, timer_count_in, allow_ot, count_direction):
  # Load settings for bonspiel
  settings = [
    {"key": "game_type", "value": "bonspiel"},
    {"key": "time_per_end", "value": time_per_end},
    {"key": "stones_per_end", "value": stones_per_end},
    {"key": "time_to_chime", "value": time_to_chime},
    {"key": "count_in", "value": timer_count_in},
    {"key": "allow_overtime", "value": int(allow_ot)},
    {"key": "count_direction", "value": count_direction}
  ]
  logger.info("Starting {} bonspiel with settings:".format(job_id, settings))
  for setting in settings:
    logger.info(" - Setting {} to {}".format(setting["key"], setting["value"]))
    requests.get('http://localhost:5000/update?key={}&value={}'.format(setting["key"], setting["value"]))

def end_bonspiel(job_id):
  logger.info("Ending {} bonspiel and resetting to league defaults.".format(job_id))
  # Set timer back to league defaults
  requests.get('http://localhost:5000/update?key={}&value={}'.format("game_type", "league"))
  requests.get('http://localhost:5000/load_profile?name={}'.format("8ends"))
  requests.get('http://localhost:5000/reset')

def refresh_jobs():
  """Reload new jobs from the job store."""
  for key, jobstore in jobstores.items():
    logger.debug("Refreshing jobs from jobstore: {}".format(key))
    loaded_jobs = {job.id for job in scheduler.get_jobs(jobstore=key)}
    stored_jobs = {job.id for job in jobstore.get_all_jobs()}

    new_jobs = stored_jobs - loaded_jobs
    if new_jobs:
      scheduler.remove_jobstore(key)
      scheduler.add_jobstore(jobstores[key], alias=key)

def clear_style_recycle_bin(time_limit_days=7):
  """
  Clear out files in the styles recycle bin older than time_limit_days days.
  Default is 7 days.
  """
  recycle_bin_path = os.path.join(STYES_PATH, "recycle_bin")
  if not os.path.exists(recycle_bin_path):
    return

  now = datetime.now()
  cutoff = now - timedelta(days=time_limit_days)
  cutoff = cutoff.timestamp()

  for filename in os.listdir(recycle_bin_path):
    file_path = os.path.join(recycle_bin_path, filename)
    if os.path.isfile(file_path):
      file_mtime = os.path.getmtime(file_path)
      if file_mtime < cutoff:
        try:
          os.remove(file_path)
          logger.info("Deleted recycled style file: {}".format(file_path))
        except Exception as e:
          logger.error("Error deleting file {}: {}".format(file_path, e))

if __name__ == "__main__":
  try:
    scheduler.add_job(
        refresh_jobs,
        trigger="interval",
        seconds=60,
        id="refresh_jobs",
        jobstore="memory"
    )

    scheduler.add_job(
        clear_style_recycle_bin,
        trigger="interval",
        hours=24,
        id="clear_style_recycle_bin",
        jobstore="memory"
    )

    logger.info("Starting scheduler...")
    scheduler.start()
  finally:
    scheduler.shutdown()
    logger.info("Scheduler shut down.")