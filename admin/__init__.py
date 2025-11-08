from collections import OrderedDict
import sqlite3
from enum import Enum
import os
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

DATABASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app.db'))

jobstores = {
  "default": SQLAlchemyJobStore(url="sqlite:///{}".format(DATABASE_PATH)),
  "league": SQLAlchemyJobStore(url="sqlite:///{}".format(DATABASE_PATH), tablename='league_jobs'),
  "bonspiel": SQLAlchemyJobStore(url="sqlite:///{}".format(DATABASE_PATH), tablename='bonspiel_jobs'),
  }
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start(paused=True)


class Permissions(Enum):
  MANAGE_USERS             = 0b000000000001
  MANAGE_LEAGUE_SCHEDULE   = 0b000000000010
  MANAGE_BONSPIEL_SCHEDULE = 0b000000000100
  MANAGE_PROFILES          = 0b000000001000
  VIEW_SCHEDULE            = 0b000000010000

def load_profiles(db_path):
  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()

  cursor.execute("""
  CREATE TABLE IF NOT EXISTS server_profiles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      time_per_end INT,
      num_ends INT,
      count_direction INT,
      allow_overtime INT,
      stones_per_end INT,
      description TEXT
  )
  """)

  cursor.execute("SELECT name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description FROM server_profiles")
  rows = cursor.fetchall()
  if not rows:
    cursor.execute("INSERT INTO server_profiles (name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description) VALUES (?, ?, ?, ?, ?, ?, ?)",("8ends", 900, 8, -1, 0, 8, "Standard 8 end game."))
    cursor.execute("INSERT INTO server_profiles (name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description) VALUES (?, ?, ?, ?, ?, ?, ?)",("6ends", 900, 6, -1, 0, 8, "Standard 6 end game."))
    cursor.execute("INSERT INTO server_profiles (name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description) VALUES (?, ?, ?, ?, ?, ?, ?)",("doubles", 675, 8, -1, 0, 5, "Standard 8 end doubles game."))
    cursor.execute("SELECT name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description FROM server_profiles")
    rows = cursor.fetchall()
    conn.commit()
  conn.close()

  profiles = OrderedDict()
  for row in rows:
    name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description = row
    profiles[name] = {
        "time_per_end": time_per_end,
        "num_ends": num_ends,
        "count_direction": count_direction,
        "allow_overtime": bool(allow_overtime),
        "stones_per_end": stones_per_end,
        "description": description
    }
  return profiles