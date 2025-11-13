from flask import Blueprint, render_template, abort
from flask import Flask, session, redirect, url_for, request, render_template_string, flash
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import sqlite3
import os
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
from urllib.parse import urlparse, urljoin
from . import load_profiles, Permissions, DATABASE_PATH, scheduler, jobstores
import json
import copy

admin = Blueprint('admin', __name__, template_folder="templates")

# Active sessions stored server-side
active_sessions = {}

def is_safe_url(target):
  ref_url = urlparse(request.host_url)
  test_url = urlparse(urljoin(request.host_url, target))
  return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

# Helper decorator to protect routes
def protected_route(f):
  def wrapper(*args, **kwargs):
    sid = session.get('session_id')
    if not sid or sid not in active_sessions:
      return redirect(url_for('admin.index', next=request.url))
    return f(*args, **kwargs)
  wrapper.__name__ = f.__name__
  return wrapper

def user_permissions():
  sid = session.get('session_id')
  return active_sessions[sid]['permissions'] if sid in active_sessions else None

def check_permissions(required):
  perms = user_permissions()
  if perms is not None and (perms & required.value):
    return True
  return False

@admin.route('/')
def index():
    pages = []
    next_url = request.args.get('next')

    if next_url and not is_safe_url(next_url):
        next_url = None

    display_order = [
        Permissions.MANAGE_USERS,
        Permissions.MANAGE_PROFILES,
        Permissions.MANAGE_LEAGUE_SCHEDULE,
        Permissions.MANAGE_BONSPIEL_SCHEDULE,
    ]
    for perm in Permissions:
      if perm not in display_order:
        display_order.append(perm)

    for perm in display_order:
        if check_permissions(perm):
            pages.append({
                "endpoint": "admin.{:s}".format(perm.name.lower()),
                "name": perm.name.replace('_', ' ').title()
            })

    return render_template(
        "admin/index.html",
        active_sessions=active_sessions,
        pages=pages,
        next=next_url
    )

@admin.route('/login', methods=['POST'])
def login():
  username = request.form['username']
  password = request.form['password']
  next_page = request.form.get('next', None)

  conn = sqlite3.connect(DATABASE_PATH)
  cursor = conn.cursor()
  cursor.execute("SELECT * FROM users WHERE username=?", (username,))
  row = cursor.fetchone()
  conn.close()

  user_id, full_name, email, db_username, db_hash, permissions = row if row else (None, None, None, None, None, None)

  if row and check_password_hash(db_hash, password):
    session_id = str(uuid.uuid4())
    session['session_id'] = session_id
    active_sessions[session_id] = {"username": username, "permissions": permissions}
    flash('Login successful!')
  else:
    flash('Invalid credentials.')

  if next_page and is_safe_url(next_page):
    return redirect(next_page)
  else:
    return redirect(url_for('admin.index'))

def add_league_job():
  job_id = request.form['job_id']
  day_of_week = request.form['day_of_week']
  start_time_str = request.form['start_time']
  profile = request.form['profile']

  start_time = datetime.strptime(start_time_str, "%H:%M")
  hour = start_time.hour
  minute = start_time.minute

  if scheduler.get_job(job_id):
    flash('Job ID already exists!')
    return redirect(url_for('admin.manage_league_schedule'))

  scheduler.add_job(
    id=job_id,
    name="league",
    func="timer_scheduler:start_timer",
    args=[profile],
    trigger="cron",
    day_of_week=day_of_week,
    hour=hour,
    minute=minute,
    replace_existing=False,
    jobstore='league'
  )
  flash('Job added successfully!')

def edit_league_job():
  job_id = request.form['job_id']
  day_of_week = request.form['day_of_week']
  start_time_str = request.form['start_time']
  profile = request.form['profile']

  start_time = datetime.strptime(start_time_str, "%H:%M")
  hour = start_time.hour
  minute = start_time.minute

  job = scheduler.get_job(job_id)
  if not job:
    flash('Job not found!')
    return redirect(url_for('admin.manage_league_schedule'))

  trigger = CronTrigger(
      day_of_week=day_of_week,
      hour=int(hour),
      minute=int(minute)
  )

  scheduler.modify_job(
    job_id,
    trigger=trigger,
    args=[profile]
  )
  flash('Job updated successfully!')

def delete_league_job():
  job_id = request.form['job_id']
  job = scheduler.get_job(job_id)
  if not job:
    flash('Job not found!')
    return redirect(url_for('admin.manage_league_schedule'))

  scheduler.remove_job(job_id)
  flash('Job deleted successfully!')

def pause_resume_league_job():
  job_id = request.form['job_id']
  job = scheduler.get_job(job_id)
  if not job:
    flash('Job not found!')
    return redirect(url_for('admin.manage_league_schedule'))

  if job.next_run_time is None:
    scheduler.resume_job(job_id, jobstore='league')
    flash('Job resumed successfully!')
  else:
    scheduler.pause_job(job_id, jobstore='league')
    flash('Job paused successfully!')

@admin.route('/league_scheduler', methods=['GET', 'POST'])
@protected_route
def manage_league_schedule():
  if not check_permissions(Permissions.MANAGE_LEAGUE_SCHEDULE):
    return redirect(url_for('admin.unauthorized'))

  if request.method == 'POST':
    action = request.form['action']

    if action == 'add':
      add_league_job()
    elif action == 'delete':
      delete_league_job()
    elif action == 'edit':
      edit_league_job()
    elif action == "pause_resume":
      pause_resume_league_job()

  jobs = scheduler.get_jobs(jobstore='league')
  jobs.sort(key=lambda j: j.next_run_time.replace(tzinfo=None) if j.next_run_time else datetime.max)
  jobs = [
      {
        "id": job.id,
        "day_of_week": str(job.trigger.fields[4]),
        "hour": int(str(job.trigger.fields[5])),
        "minute": int(str(job.trigger.fields[6])),
        "paused": job.next_run_time is None,
        "profile": job.args[0]
      } for job in jobs
  ]
  profiles = load_profiles(DATABASE_PATH)
  return render_template("admin/league_scheduler.html", jobs=jobs, profiles=profiles)

def add_bonspiel_job():
  job_id = request.form['job_id']
  start_dt_str = request.form['start_datetime']
  end_dt_str = request.form['end_datetime']

  start_dt = datetime.fromisoformat(start_dt_str)
  end_dt = datetime.fromisoformat(end_dt_str)

  time_to_chime = int(request.form['time_to_chime'])
  time_per_end = int(request.form['time_per_end'])
  stones_per_end = int(request.form['stones_per_end'])
  timer_count_in = int(request.form['timer_count_in'])
  allow_ot = request.form.get('allow_ot', 'off') == 'on'
  count_direction = -1 if request.form.get('count_direction', 'down') == 'down' else 1

  if scheduler.get_job(job_id):
    flash('Job ID already exists!')
    return redirect(url_for('admin.manage_bonspiel_schedule'))

  scheduler.add_job(
    id=job_id,
    name="bonspiel_start",
    func="timer_scheduler:start_bonspiel",
    args=[job_id, time_to_chime, time_per_end, stones_per_end, timer_count_in, allow_ot, count_direction],
    trigger="cron",
    year=start_dt.year,
    month=start_dt.month,
    day=start_dt.day,
    hour=start_dt.hour,
    minute=start_dt.minute,
    replace_existing=False,
    jobstore='bonspiel'
  )

  scheduler.add_job(
    id="{:s}_end".format(job_id),
    name="bonspiel_end",
    func="timer_scheduler:end_bonspiel",
    args=[job_id],
    trigger="cron",
    year=end_dt.year,
    month=end_dt.month,
    day=end_dt.day,
    hour=end_dt.hour,
    minute=end_dt.minute,
    replace_existing=False,
    jobstore='bonspiel'
  )
  flash('Job added successfully!')

def delete_bonspiel_job():
  job_id = request.form['job_id']
  start_job = scheduler.get_job(job_id)
  end_job = scheduler.get_job("{:s}_end".format(job_id))
  if not start_job or not end_job:
    flash('Job not found!')
    return redirect(url_for('admin.manage_bonspiel_schedule'))

  scheduler.remove_job(job_id)
  scheduler.remove_job("{:s}_end".format(job_id))
  flash('Job deleted successfully!')

def edit_bonspiel_job():
  job_id = request.form['job_id']
  start_dt_str = request.form['start_datetime']
  end_dt_str = request.form['end_datetime']

  start_dt = datetime.fromisoformat(start_dt_str)
  end_dt = datetime.fromisoformat(end_dt_str)

  time_to_chime = int(request.form['time_to_chime'])
  time_per_end = int(request.form['time_per_end'])
  stones_per_end = int(request.form['stones_per_end'])
  timer_count_in = int(request.form['timer_count_in'])
  allow_ot = request.form.get('allow_ot', 'off') == 'on'
  count_direction = -1 if request.form.get('count_direction', 'down') == 'down' else 1

  start_job = scheduler.get_job(job_id)
  end_job = scheduler.get_job("{:s}_end".format(job_id))
  if not start_job or not end_job:
    flash('Job not found!')
    return redirect(url_for('admin.manage_bonspiel_schedule'))

  start_trigger = CronTrigger(
      year=int(start_dt.year),
      month=int(start_dt.month),
      day=int(start_dt.day),
      hour=int(start_dt.hour),
      minute=int(start_dt.minute)
  )
  end_trigger = CronTrigger(
      year=int(end_dt.year),
      month=int(end_dt.month),
      day=int(end_dt.day),
      hour=int(end_dt.hour),
      minute=int(end_dt.minute)
  )

  scheduler.modify_job(
    job_id,
    trigger=start_trigger,
    args=[job_id, time_to_chime, time_per_end, stones_per_end, timer_count_in, allow_ot, count_direction],
  )
  scheduler.modify_job(
    "{:s}_end".format(job_id),
    trigger=end_trigger,
  )
  flash('Job updated successfully!')

@admin.route('/bonspiel_scheduler', methods=['GET', 'POST'])
@protected_route
def manage_bonspiel_schedule():
  if not check_permissions(Permissions.MANAGE_BONSPIEL_SCHEDULE):
    return redirect(url_for('admin.unauthorized'))

  if request.method == 'POST':
    action = request.form['action']
    if action == 'add':
      add_bonspiel_job()
    elif action == 'delete':
      delete_bonspiel_job()
    elif action == 'edit':
      edit_bonspiel_job()

  jobs = list(filter(lambda j: j.name == "bonspiel_start", scheduler.get_jobs(jobstore='bonspiel')))
  jobs.sort(key=lambda j: j.next_run_time.replace(tzinfo=None) if j.next_run_time else datetime.max)

  jobs = [
      {
        "id": job.id,
        "start_dt": datetime(year=int(str(job.trigger.fields[0])),
                             month=int(str(job.trigger.fields[1])),
                             day=int(str(job.trigger.fields[2])),
                             hour=int(str(job.trigger.fields[5])),
                             minute=int(str(job.trigger.fields[6]))),
        "end_dt": datetime(year=int(str(scheduler.get_job("{:s}_end".format(job.id)).trigger.fields[0])),
                           month=int(str(scheduler.get_job("{:s}_end".format(job.id)).trigger.fields[1])),
                           day=int(str(scheduler.get_job("{:s}_end".format(job.id)).trigger.fields[2])),
                           hour=int(str(scheduler.get_job("{:s}_end".format(job.id)).trigger.fields[5])),
                           minute=int(str(scheduler.get_job("{:s}_end".format(job.id)).trigger.fields[6]))),
        "time_to_chime": job.args[1],
        "time_per_end": job.args[2],
        "stones_per_end": job.args[3],
        "timer_count_in": job.args[4],
        "allow_ot": job.args[5],
        "count_direction": job.args[6]
      } for job in jobs
  ]
  return render_template("admin/bonspiel_scheduler.html", jobs=jobs)

def add_profile(conn):
  cursor = conn.cursor()

  name = request.form['name']
  cursor.execute("SELECT name FROM server_profiles WHERE name=?", (name,))
  if cursor.fetchone():
    flash('Profile name already exists!')
    return redirect(url_for('admin.manage_profiles'))

  time_per_end = int(request.form['time_per_end'])
  num_ends = int(request.form['num_ends'])
  count_direction = -1 if request.form.get('count_direction', 'down') == 'down' else 1
  allow_overtime = request.form.get('allow_overtime', 'off') == 'on'
  stones_per_end = int(request.form['stones_per_end'])
  description = request.form['description']

  cursor.execute("""INSERT INTO server_profiles (name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description))
  conn.commit()
  conn.close()
  flash('Profile added successfully!')

def edit_profile(conn):
  cursor = conn.cursor()

  original_name = request.form['original_name']
  cursor.execute("SELECT name FROM server_profiles WHERE name=?", (original_name,))

  if not cursor.fetchone():
    flash('Profile not found!')
    return redirect(url_for('admin.manage_profiles'))

  name = request.form['name']
  time_per_end = int(request.form['time_per_end'])
  num_ends = int(request.form['num_ends'])
  count_direction = -1 if request.form.get('count_direction', 'down') == 'down' else 1
  allow_overtime = request.form.get('allow_overtime', 'off') == 'on'
  stones_per_end = int(request.form['stones_per_end'])
  description = request.form['description']

  cursor.execute("""UPDATE server_profiles
                    SET name=?, time_per_end=?, num_ends=?, count_direction=?, allow_overtime=?, stones_per_end=?, description=?
                    WHERE name=?""",
                  (name, time_per_end, num_ends, count_direction, allow_overtime, stones_per_end, description, original_name))
  conn.commit()
  flash('Profile updated successfully!')

  conn.close()

def delete_profile(conn):
  cursor = conn.cursor()

  original_name = request.form['original_name']
  cursor.execute("SELECT name FROM server_profiles WHERE name=?", (original_name,))

  if cursor.fetchone():
    cursor.execute("DELETE FROM server_profiles WHERE name=?", (original_name,))
    conn.commit()
    flash('Profile deleted successfully!')
  else:
    flash('Profile not found!')

  conn.close()

@admin.route('/profiles', methods=['GET', 'POST'])
@protected_route
def manage_profiles():
  if not check_permissions(Permissions.MANAGE_PROFILES):
    return redirect(url_for('admin.unauthorized'))

  if request.method == 'POST':
    action = request.form['action']
    try:
      conn = sqlite3.connect(DATABASE_PATH)
      if action == 'add':
        add_profile(conn)
      elif action == 'delete':
        delete_profile(conn)
      elif action == 'edit':
        edit_profile(conn)
    finally:
      conn.close()

  return render_template("admin/profiles.html", profiles=load_profiles(DATABASE_PATH))

@admin.route('/change_password', methods=['GET', 'POST'])
@protected_route
def change_password():
  if request.method == 'POST':
    current_password = request.form['current_password']
    new_password = request.form['new_password']

    sid = session.get('session_id')
    username = active_sessions[sid]['username']

    try:
      conn = sqlite3.connect(DATABASE_PATH)
      cursor = conn.cursor()

      cursor.execute("SELECT * FROM users WHERE username=?", (username,))
      row = cursor.fetchone()

      if row and check_password_hash(row[2], current_password):
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET hash=? WHERE username=?", (new_hash, username))
        conn.commit()
        flash('Password changed successfully!')
      else:
        flash('Current password is incorrect.')
    finally:
      conn.close()

  return render_template("admin/change_password.html")

def add_user(conn):
  cursor = conn.cursor()

  username = request.form['username']
  full_name = request.form['full_name']
  email = request.form['email']
  if cursor.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone():
    flash('Username already exists!')
    return redirect(url_for('admin.manage_users'))

  password = request.form['password']
  pw_hash = generate_password_hash(password)
  permissions = 0
  cursor.execute("INSERT INTO users (full_name, email, username, hash, permissions) VALUES (?, ?, ?, ?, ?)", (full_name, email, username, pw_hash, permissions))
  conn.commit()
  flash('User added successfully!')

def edit_user(conn):
  cursor = conn.cursor()

  user_id = int(request.form['user_id'])
  permissions = 0
  for perm in Permissions:
    perm_value = request.form.get(perm.name, "off") == "on"
    permissions |= (perm.value if perm_value else 0)
  cursor.execute("UPDATE users SET permissions=? WHERE id=?", (permissions, user_id))
  conn.commit()
  flash('User permissions updated successfully!')

def delete_user(conn):
  cursor = conn.cursor()

  user_id = int(request.form['user_id'])
  row = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
  if not row:
    flash('User not found!')
    return redirect(url_for('admin.manage_users'))
  username = row[1]

  cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
  conn.commit()
  flash('User deleted successfully!')

  for sid, info in list(active_sessions.items()):
    if info['username'] == username:
      active_sessions.pop(sid)

@admin.route('/users', methods=['GET','POST'])
@protected_route
def manage_users():
  if not check_permissions(Permissions.MANAGE_USERS):
    return redirect(url_for('admin.unauthorized'))

  conn = sqlite3.connect(DATABASE_PATH)
  cursor = conn.cursor()

  try:
    if request.method == 'POST':
      action = request.form['action']

      if action == 'add':
        add_user(conn)
      elif action == 'delete':
        delete_user(conn)
      elif action == 'edit':
        edit_user(conn)

    cursor.execute("SELECT id, full_name, email, username, permissions FROM users")
    users = cursor.fetchall()
  finally:
    conn.close()

  users = [{
    "id": row[0],
    "full_name": row[1],
    "email": row[2],
    "username": row[3],
    "permissions": {perm.name.replace('_', ' ').title(): (row[4] & perm.value) != 0 for perm in Permissions}
  } for row in users]

  return render_template("admin/users.html", users=users)

@admin.route('/view_schedule')
@protected_route
def view_schedule():
  if not check_permissions(Permissions.VIEW_SCHEDULE):
    return redirect(url_for('admin.unauthorized'))

  jobs = scheduler.get_jobs()
  jobs = list(filter(lambda j: j.next_run_time is not None, jobs))
  jobs.sort(key=lambda j: j.next_run_time)

  # Filter out jobs which would run during a bonspiel. They are paused when the bonspiel begins,
  # but before that we need to filter them out to not show them.
  bonspiel_jobs = filter(lambda j: j.name == "bonspiel_start", scheduler.get_jobs(jobstore='bonspiel'))
  if bonspiel_jobs:
    for start_job in bonspiel_jobs:
      start_dt = datetime(year=int(str(start_job.trigger.fields[0])),
                           month=int(str(start_job.trigger.fields[1])),
                           day=int(str(start_job.trigger.fields[2])),
                           hour=int(str(start_job.trigger.fields[5])),
                           minute=int(str(start_job.trigger.fields[6])))
      end_job = scheduler.get_job("{:s}_end".format(start_job.id))
      end_dt = datetime(year=int(str(end_job.trigger.fields[0])),
                         month=int(str(end_job.trigger.fields[1])),
                         day=int(str(end_job.trigger.fields[2])),
                         hour=int(str(end_job.trigger.fields[5])),
                         minute=int(str(end_job.trigger.fields[6])))

      jobs = filter(lambda j: not (start_dt < j.next_run_time.replace(tzinfo=None) < end_dt), jobs)

  jobs = [
      {
        "id": job.id,
        "next_run_time": job.next_run_time,
        "description": "{} league".format(job.args[0]) if job.name == "league" else "bonspiel start" if job.name == "bonspiel_start" else "bonspiel end"
      } for job in jobs
  ]

  return render_template("admin/view_schedule.html", jobs=jobs)

@admin.route('/register')
def register():
  return render_template("admin/register.html")

@admin.route('/add_user', methods=['POST'])
def add_user():
  full_name = request.form['full_name']
  email = request.form['email']
  username = request.form['username']
  password = request.form['password']
  confirm_password = request.form['confirm_password']
  if password != confirm_password:
    flash("Passwords do not match!")
    return redirect(request.referrer)

  pw_hash = generate_password_hash(password)

  conn = sqlite3.connect(DATABASE_PATH)
  cursor = conn.cursor()

  cursor.execute("""
  CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      full_name TEXT,
      email TEXT,
      username TEXT NOT NULL,
      hash TEXT NOT NULL,
      permissions INT DEFAULT 0
  )
  """)

  cursor.execute("SELECT * FROM users")
  if not cursor.fetchone():
    # First user, give all permissions
    permissions = 0
    for perm in Permissions:
      permissions |= perm.value
    cursor.execute("INSERT INTO users (full_name, email, username, hash, permissions) VALUES (?, ?, ?, ?, ?)", (full_name, email, username, pw_hash, permissions))
    conn.commit()
    conn.close()
    flash('Admin user registered successfully with all permissions! You can now log in.')
    return redirect(url_for('admin.index'))

  cursor.execute("SELECT * FROM users WHERE username=?", (username,))
  if cursor.fetchone():
    flash('Username already exists!')
    conn.close()
    return redirect(url_for('admin.register'))

  cursor.execute("INSERT INTO users (full_name, email, username, hash, permissions) VALUES (?, ?, ?, ?, ?)", (full_name, email, username, pw_hash, 0))
  conn.commit()
  conn.close()
  flash('User registered successfully! You can now log in.')
  return redirect(url_for('admin.index'))

@admin.route('/upload_styles', methods=['GET', 'POST'])
@protected_route
def upload_styles():
  if not check_permissions(Permissions.UPLOAD_STYLES):
    return redirect(url_for('admin.unauthorized'))

  from app import load_default_styles
  # load_default_styles is cached, so we need to make a copy of the returned value
  # to avoid modifying the original
  styles = copy.deepcopy(load_default_styles())

  for style in styles["colors"]:
    styles["colors"][style] = "#{:02x}{:02x}{:02x}".format(*styles["colors"][style])


  if request.method == 'POST':
    style_name = request.form['style_name']
    style_name = style_name.strip().replace(" ", "_").lower()
    file_data = request.files['style_file']
    if file_data:
      styles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'app_styles')
      if not os.path.exists(styles_dir):
        os.makedirs(styles_dir)

      file_path = os.path.join(styles_dir, "{:s}.json".format(style_name))
      style_json = file_data.read().decode('utf-8')
      style = json.loads(style_json)

      allowed_keys = ("colors", "parameters")
      for key in style.keys():
        if not (key in allowed_keys):
          del style[key]

      with open(file_path, 'w') as outfile:
        json.dump(style, outfile, indent=4)
      flash('Style uploaded successfully!')
    else:
      flash('No file selected for upload.')
  return render_template("admin/upload_style.html", styles=styles)

@admin.route('/change_styles', methods=['GET', 'POST'])
@protected_route
def change_styles():
  if not check_permissions(Permissions.CHANGE_STYLES):
    return redirect(url_for('admin.unauthorized'))

  styles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'app_styles')
  style_files = os.listdir(styles_dir) if os.path.exists(styles_dir) else []
  style_files = filter(lambda f: f.endswith('.json') and not os.path.islink(os.path.join(styles_dir, f)), style_files)

  if request.method == 'POST':
    selected_style = request.form['style_file']

    file_path = os.path.join(styles_dir, "{:s}.json".format(selected_style))
    tmp_name = "{:s}_tmp.json".format(str(uuid.uuid4()))
    os.symlink(file_path, os.path.join(styles_dir, tmp_name))
    os.replace(os.path.join(styles_dir, tmp_name), os.path.join(styles_dir, "user_styles.json"))
    flash('Style changed successfully!')

  return render_template("admin/change_styles.html", style_files=[os.path.splitext(f)[0] for f in style_files])

@admin.route('/logout')
def logout():
  sid = session.pop('session_id', None)
  if sid and sid in active_sessions:
    active_sessions.pop(sid)
  return redirect(url_for('index'))

@admin.route('/unauthorized')
def unauthorized():
  return render_template("admin/unauthorized.html"), 401