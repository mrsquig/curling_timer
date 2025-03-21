from flask import Flask, jsonify, request, render_template, send_file
from datetime import datetime
from config import ConfigValue, bool_type
from collections import OrderedDict
import copy
import json
import argparse
import time
import sys
import os
import io

try:
  USING_WAITRESS = True
  import waitress
except ImportError:
  USING_WAITRESS = False

PROFILES = OrderedDict()
PROFILE_ID = 0
MESSAGES = []

def timestamp():
  return datetime.now().timestamp()

app = Flask(__name__)
server_config = {
    "version": ConfigValue(0.1),
    "time_per_end": ConfigValue(15*60, int),
    "num_ends": ConfigValue(8, int),
    "start_timestamp": ConfigValue(timestamp(), int),
    "stop_timestamp": ConfigValue(timestamp(), int),
    "timer_stop_uptime": ConfigValue(0, int),
    "count_direction": ConfigValue(-1, int),
    "allow_overtime": ConfigValue(False, bool_type),
    "is_timer_running": ConfigValue(False, bool_type),
    "stones_per_end": ConfigValue(8, int),
    "is_game_complete": ConfigValue(False, bool_type),
    "count_in": ConfigValue(0, int),
    "time_to_chime": ConfigValue(6000, int),
    "game_type": ConfigValue("league", str)
}

@app.route('/', methods=['GET','POST'])
def index():
  if request.method == 'POST':
    if "Start" in request.form:
      # If previous game is done (timer done counting and overtime not allowed), then reset timer and start again
      if server_config["is_game_complete"].value:
        reset_timer()

      start_timer()
    elif "Stop" in request.form:
      stop_timer()
    elif "Reset" in request.form:
      reset_timer()
    elif "LoadProfile" in request.form:
      if server_config["is_timer_running"].value and server_config["game_type"].value == "bonspiel":
        return jsonify({"error": "Cannot update config while timer is running in bonspiel mode"}), 400

      profile_name = request.form.get('profile_name')
      update_config_with_profile(profile_name)
    elif "AdjustTimer" in request.form:
      adjustDir = request.form.get('adjust_minutes_dir')
      adjustVal = request.form.get('adjust_minutes')
      adjust_timer(adjustDir, adjustVal)
    else:
      if server_config["is_timer_running"].value and server_config["game_type"].value == "bonspiel":
        return jsonify({"error": "Cannot update config while timer is running in bonspiel mode"}), 400

      # In bonspiel mode the number of ends is calculated automatically
      update_config("game_type", request.form.get("game_type"))
      if server_config["game_type"].value != "bonspiel":
        update_config("num_ends", request.form.get("num_ends"))
      else:
        update_config("time_to_chime", request.form.get("time_to_chime"))

      update_config("time_per_end", request.form.get("time_per_end"))
      update_config("count_direction", request.form.get("count_direction"))
      update_config("allow_overtime", request.form.get("allow_overtime"))
      update_config("stones_per_end", request.form.get("stones_per_end"))
      update_config("count_in", request.form.get("count_in"))

  data = {key: value.value for key,value in server_config.items()}
  data["profiles"] = PROFILES.keys()
  data["selected_profile_name"] = request.form.get('profile_name', None)

  response, status = get_times()
  times = response.json.get("times")
  data.update(times)
  return render_template('index.html', **data)

@app.route('/style_preview', methods=['GET'])
def style_preview():
  from app import load_default_styles
  # load_default_styles is cached, so we need to make a copy of the returned value
  # to avoid modifying the original
  styles = copy.deepcopy(load_default_styles())

  for style in styles["colors"]:
    styles["colors"][style] = "#{:02x}{:02x}{:02x}".format(*styles["colors"][style])

  return render_template('style_preview.html', styles=styles)

def get_style_image(end_num, styles, percent=0.25):
  import app
  img_io = io.BytesIO()
  clock = app.IceClock(headless=True, styles=styles)
  clock._server_config = {k: v.value for k,v in server_config.items()}
  total_time = server_config["time_per_end"].value * server_config["num_ends"].value
  elapsed = server_config["time_per_end"].value * (end_num - 1) + percent * server_config["time_per_end"].value

  clock._hours = int((total_time-elapsed) // 3600)
  clock._minutes = int(((total_time-elapsed) // 60) % 60)
  clock._seconds = int((total_time-elapsed) % 60)
  clock._end_number = end_num
  clock._end_percentage = percent
  clock._is_overtime = False
  clock._uptime = elapsed
  clock.render_to_image(img_io)

  img_io.seek(0)
  return img_io

@app.route('/style_img', methods=['POST'])
def style_img():
  input_data = request.get_json()
  styles=input_data["styles"]

  styles["colors"] = {k: tuple(v) for k,v in styles["colors"].items()}
  if input_data["image_settings"]["image_type"] == "normal":
    end_num = 1
    end_percent = 0.25
  elif input_data["image_settings"]["image_type"] == "warning_1":
    end_num = server_config["num_ends"].value - 1
    end_percent = 0.5
  elif input_data["image_settings"]["image_type"] == "warning_2":
    end_num = server_config["num_ends"].value
    end_percent = 0.5
  else:
    return jsonify({"error": "Invalid image type provided"}), 400

  img_io = get_style_image(end_num, styles, percent = end_percent)

  return send_file(img_io, mimetype='image/png')

@app.route('/download_style', methods=['POST'])
def download_style():
  input_data = request.get_json()
  styles=input_data["styles"]
  styles["colors"] = {k: tuple(v) for k,v in styles["colors"].items()}
  output_content = json.dumps(styles, indent=2)

  file_stream = io.BytesIO()
  file_stream.write(output_content.encode('utf-8'))
  file_stream.seek(0)

  return send_file(file_stream, as_attachment=True, download_name="user_styles.json", mimetype="text/plain")

@app.route('/version', methods=['GET'])
def get_version():
  return jsonify({"version": server_config["version"]})

@app.route('/config', methods=['GET'])
def query_key():
  key = request.args.get('key')
  if not key:
    return jsonify(server_config), 200

  if key in server_config:
    return jsonify({key: server_config[key].value}), 200
  else:
    return jsonify({"error": "Key not found"}), 404

def calc_num_bonspiel_ends():
  if server_config["game_type"].value != "bonspiel":
    return
  time_to_chime = server_config["time_to_chime"].value
  time_per_end = server_config["time_per_end"].value
  # int rounds down, so if the chime occurs during an end we need to add
  # that end, then one more.
  server_config["num_ends"].value = int(time_to_chime/time_per_end) + 2

@app.route('/update', methods=['GET'])
def update_config_route():
  if server_config["is_timer_running"].value and server_config["game_type"].value == "bonspiel":
    return jsonify({"error": "Cannot update config while timer is running in bonspiel mode"}), 400

  key = request.args.get('key')
  if not key:
    return jsonify({"error": "No key provided"}), 400
  if key not in server_config:
    return jsonify({"error": "Key not found"}), 500

  if server_config["game_type"].value == "bonspiel" and key == "num_ends":
    return jsonify({"error": "Number of ends cannot be updated in bonspiel mode"}), 400
  calc_num_bonspiel_ends()


  new_value = request.args.get("value")
  if new_value:
    update_config(key, new_value)
    return jsonify({key: server_config[key].value}), 200
  return jsonify({"error": "No value provided"}), 400

def update_config(key, new_value):
  global server_config
  server_config[key].value = new_value
  calc_num_bonspiel_ends()

@app.route('/start', methods=['GET'])
def start_timer():
  global server_config
  server_config["is_timer_running"].value = True

  #if the timer was already paused, need to account for the amount of time the timer
  #had already elapsed. Otherwise this would essentially reset the timer.
  server_config["start_timestamp"].value = timestamp() - server_config["timer_stop_uptime"].value

  return jsonify({"start_timestamp": server_config["start_timestamp"].value}), 200

@app.route('/stop', methods=['GET'])
def stop_timer():
  global server_config
  server_config["is_timer_running"].value = False
  server_config["stop_timestamp"].value = timestamp()

  #update the uptime each time we stop, so we know how much time had already elapsed at the time of stoppage
  server_config["timer_stop_uptime"].value = server_config["stop_timestamp"].value - server_config["start_timestamp"].value

  return jsonify({"stop_timestamp": server_config["stop_timestamp"].value}), 200

@app.route('/reset', methods=['GET'])
def reset_timer():
  global server_config
  time = request.args.get('time')
  if not time:
    server_config["start_timestamp"].value = timestamp()
    server_config["stop_timestamp"].value = timestamp()
  else:
    server_config["start_timestamp"].value = time
    server_config["stop_timestamp"].value = time

  server_config["is_game_complete"].value = False
  server_config["timer_stop_uptime"].value = 0

  #always stop timer when reseting time
  server_config["is_timer_running"].value = False

  server_config["count_in"].value = 0

  return jsonify({"start_timestamp": server_config["start_timestamp"].value}), 200

@app.route('/game_times', methods=['GET'])
def get_times():
  global server_config
  # Get how long the timer has been running
  if server_config["is_timer_running"].value and server_config["count_in"].value > 0:
    server_config["count_in"].value -= 1
    uptime = 0
  elif server_config["is_timer_running"].value == True:
    current_time = timestamp()
    uptime = int(current_time) - server_config["start_timestamp"].value
  else:
    current_time = server_config["stop_timestamp"].value
    uptime = int(current_time) - server_config["start_timestamp"].value

  # Initialize results dictionary
  times = {}
  times["uptime"] = uptime

  # End number and percentage are always based on the uptime of the timer
  times["end_number"] = uptime // server_config["time_per_end"].value + 1
  times["end_percentage"] = uptime/server_config["time_per_end"].value - times["end_number"] + 1

  # Calculate the total time of the game, then figure out which time to split into
  # hours, minutes, and seconds depending on if we're counting down or up
  league_time = server_config["time_per_end"].value * server_config["num_ends"].value
  if server_config["game_type"].value != "bonspiel":
    times["total_time"] = league_time
  else:
    times["total_time"] = server_config["time_to_chime"].value
  game_time = times["total_time"] - uptime if server_config["count_direction"].value < 0 else uptime

  # Determine if we're over time or not. If allow_overtime is false, then the over time flag will always be false
  times["is_overtime"] = uptime > times["total_time"] and server_config["allow_overtime"].value

  # If we don't allow overtime and the timer is done, directly call the stop function so timing stops
  # and set the time to 0 or total time, so it stays that way
  if uptime >= league_time and not server_config["allow_overtime"].value:
    stop_timer()
    game_time = 0 if server_config["count_direction"].value < 0 else times["total_time"]
    server_config["is_game_complete"].value = True
  else:
    server_config["is_game_complete"].value = False

  # If we're over time, then return how far over time we are
  if times["is_overtime"] and server_config["count_direction"].value < 0:
    game_time = game_time*-1

  # Divide the time into hours, minutes, seconds
  if not server_config["count_in"].value:
    times["hours"] = game_time // 3600
    times["minutes"] = (game_time // 60) % 60
    times["seconds"] = game_time % 60
  else:
    times["hours"] = server_config["count_in"].value // 3600
    times["minutes"] = (server_config["count_in"].value // 60) % 60
    times["seconds"] = server_config["count_in"].value % 60

  # Include the server config in the returned value for convenience and to limit
  # network traffic required to update the front end
  retVal = {"times": times, "config": {key: server_config[key].value for key in server_config}}
  return jsonify(retVal), 200

@app.route('/load_profile', methods=['GET'])
def load_profile():
  global server_config
  if server_config["is_timer_running"].value and server_config["game_type"].value == "bonspiel":
    return jsonify({"error": "Cannot update config while timer is running in bonspiel mode"}), 400

  name = request.args.get('name')
  if not name:
    return jsonify({"error": "Profile name not specified"}), 400

  if name not in PROFILES:
    return jsonify({"error": "Profile not found"}), 400

  update_config_with_profile(name)
  return jsonify({key: server_config[key].value for key in server_config}), 200

@app.route('/get_profile_description', methods=['POST'])
def get_profile_description():
  profile_name = request.get_json()

  if not profile_name:
    return jsonify({"error": "Profile name not specified"}), 400

  if profile_name not in PROFILES:
    return jsonify({"error": "Profile not found"}), 400

  return jsonify({"description": PROFILES[profile_name]["description"]}), 200

@app.route('/messages', methods=['GET'])
def get_messages():
  global MESSAGES
  output_messages = []
  for message in MESSAGES:
    output_messages.append(message)
  MESSAGES = []
  return jsonify({"messages": output_messages, "config": {key: server_config[key].value for key in server_config}}), 200

@app.route('/broadcast', methods=["GET", "POST"])
def broadcast_message():
  global MESSAGES
  if request.method == "POST":
    message = request.form.get('message', "")
    if not message:
      return render_template('broadcast_message.html', error="No message provided"), 200

    if server_config["is_timer_running"].value:
      return render_template('broadcast_message.html', error="Cannot broadcast message while timer is running"), 200

    MESSAGES.append(message)

  return render_template('broadcast_message.html'), 200

@app.route('/cycle_profile', methods=['GET'])
def cycle_profile():
  global PROFILE_ID

  # If the timer is running, don't allow the profile to be cycled
  if server_config["is_timer_running"].value:
    logger.warning("Cannot cycle profile while timer is running")
    return jsonify({key: server_config[key].value for key in server_config}), 200

  profile_names = list(PROFILES.keys())
  if PROFILE_ID >= len(profile_names):
    PROFILE_ID = 0

  update_config_with_profile(profile_names[PROFILE_ID])
  MESSAGES.append("Selected profile {}".format(profile_names[PROFILE_ID]))
  PROFILE_ID += 1
  return jsonify({key: server_config[key].value for key in server_config}), 200

def update_config_with_profile(profile_name):
  if profile_name not in PROFILES:
    return

  for key in PROFILES[profile_name]:
    if key == "description":
      continue
    server_config[key].value = PROFILES[profile_name][key]

def adjust_timer(direction, minutes):
  if not minutes:
    return

  minutes = int(minutes)

  if (direction != "add" and direction != "subtract") or minutes <= 0:
    return

  if direction == "add":
    # We "add" minutes to the start time to simulate the game starting later, meaning more time left
    server_config["start_timestamp"].value += minutes * 60

    # Don't allow the start time to be in the future
    if server_config["start_timestamp"].value > timestamp():
      server_config["start_timestamp"].value = timestamp()
  else:
    # We "subtract" minutes from the start time to simulate the game starting earlier, meaning less time left
    server_config["start_timestamp"].value -= minutes * 60
    response, status = get_times()
    times = response.json.get("times")
    uptime = times["uptime"]
    game_time = times["total_time"] - uptime if server_config["count_direction"].value < 0 else uptime

    # If the adjusted time makes the game longer than it can be, adjust it back
    if game_time > server_config["time_per_end"].value * server_config["num_ends"].value:
      server_config["start_timestamp"].value += minutes * 60

  return jsonify({"start_timestamp": server_config["start_timestamp"].value}), 200

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--host", default="0.0.0.0", help="host IP to bind to")
  parser.add_argument("--port", default="5000", type=int, help="port for server to listen on")
  parser.add_argument("--profiles", default="server_profiles.json", help="file to read profiles from")
  args = parser.parse_args()

  # Load the profiles from the file if it exists
  if os.path.exists(args.profiles):
    forbidden_keys = ("version", "is_timer_running", "start_timestamp", "stop_timestamp",
                      "timer_stop_uptime", "is_game_complete")
    with open(args.profiles, 'r') as f:
      loaded_profiles = json.load(f)

      # Copy loaded profiles into the PROFILES dictionary
      for profile in loaded_profiles:
        PROFILES[profile] = loaded_profiles[profile]

    # Remove forbidden keys from the profiles
    for profile in PROFILES:
      for key in forbidden_keys:
        if key in profile:
          del profile[key]

  if USING_WAITRESS:
    waitress.serve(app, host='0.0.0.0', port=args.port)
  else:
    app.run(port=args.port)
