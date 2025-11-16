from collections import OrderedDict
import sqlite3
from enum import Enum
import os
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
import json

APP_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_PATH = os.path.abspath(os.path.join(APP_BASE, 'app.db'))
STYLES_PATH = os.path.abspath(os.path.join(APP_BASE, 'static', 'app_styles'))

jobstores = {
  "default": SQLAlchemyJobStore(url="sqlite:///{}".format(DATABASE_PATH)),
  "league": SQLAlchemyJobStore(url="sqlite:///{}".format(DATABASE_PATH), tablename='league_jobs'),
  "bonspiel": SQLAlchemyJobStore(url="sqlite:///{}".format(DATABASE_PATH), tablename='bonspiel_jobs'),
  }
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start(paused=True)

class Permissions(Enum):
  # Note: do not change existing permission values as they may be in use
  # If you wish to add new permissions, add them to the end
  # If you need to remove a permission, just mark it as deprecated but keep the value
  # If you want to change the order that pages are displayed in the admin panel, change the order in the UI code, not here
  MANAGE_USERS             = 0b000000000001
  MANAGE_LEAGUE_SCHEDULE   = 0b000000000010
  MANAGE_BONSPIEL_SCHEDULE = 0b000000000100
  MANAGE_PROFILES          = 0b000000001000
  VIEW_SCHEDULE            = 0b000000010000
  UPLOAD_STYLES            = 0b000000100000
  CHANGE_STYLES            = 0b000001000000

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
    # Load the profiles from the file if it exists
    default_profile_path = "server_profiles.json"
    default_profiles = OrderedDict()
    if os.path.exists(default_profile_path):
      allowed_keys = ("name", "time_per_end", "num_ends", "count_direction", "allow_overtime", "stones_per_end", "description")
      with open(default_profile_path, 'r') as f:
        loaded_profiles = json.load(f)

        # Copy loaded profiles into default profiles dictionary
        for profile in loaded_profiles:
          default_profiles[profile] = loaded_profiles[profile]

      # Remove forbidden keys from the profiles
      for profile in default_profiles:
        for key in default_profiles[profile].keys():
          if not (key in allowed_keys):
            del default_profiles[profile][key]
    else:
      default_profiles["8ends"] = {
          "time_per_end": 900,
          "num_ends": 8,
          "count_direction": -1,
          "allow_overtime": False,
          "stones_per_end": 8,
          "description": "Standard 8-end game with 15 minutes per end."
      }
      default_profiles["6ends"] = {
          "time_per_end": 900,
          "num_ends": 6,
          "count_direction": -1,
          "allow_overtime": False,
          "stones_per_end": 8,
          "description": "Standard 6-end game with 15 minutes per end."
      }
      default_profiles["doubles"] = {
          "time_per_end": 675,
          "num_ends": 8,
          "count_direction": -1,
          "allow_overtime": False,
          "stones_per_end": 5,
          "description": "Standard doubles game with 11.25 minutes per end and 5 stones per end."
      }

    for profile_name, profile in default_profiles.items():
      cursor.execute("INSERT INTO server_profiles (name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (profile_name,
                      profile.get("time_per_end", 900),
                      profile.get("num_ends", 8),
                      profile.get("count_direction", -1),
                      int(profile.get("allow_overtime", 0)),
                      profile.get("stones_per_end", 8),
                      profile.get("description", "")
                     ))

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