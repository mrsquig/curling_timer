from flask import Flask, jsonify, request, render_template
from datetime import datetime
from config import ConfigValue, bool_type
import argparse
import time
import sys

try:
  USING_WAITRESS = True
  import waitress
except ImportError:
  USING_WAITRESS = False

def timestamp():
  return datetime.now().timestamp()

app = Flask(__name__)
app_config = {
    "version": ConfigValue(0.1),
    "time_per_end": ConfigValue(15*60, int),
    "num_ends": ConfigValue(8, int),
    "start_timestamp": ConfigValue(timestamp(), int),
    "stop_timestamp": ConfigValue(timestamp(), int),
    "timer_stop_uptime": ConfigValue(0, int),
    "count_direction": ConfigValue(-1, int),
    "allow_overtime": ConfigValue(False, bool_type),
    "is_timer_running": ConfigValue(False, bool_type)
}

@app.route('/', methods=['GET','POST'])
def index(): 
  if request.method == 'POST':
    if "Start" in request.form:
      start_timer()
    elif "Stop" in request.form:
      stop_timer()
    elif "Reset" in request.form:
      reset_timer()
    else:
      app_config["num_ends"].value = request.form.get('num_ends')
      app_config["time_per_end"].value = request.form.get('time_per_end')
      app_config["count_direction"].value = request.form.get('count_direction')
      app_config["allow_overtime"].value = request.form.get("allow_overtime")

  data = {key: value.value for key,value in app_config.items()}
  times, status = get_times()
  data.update(times.json)
  return render_template('index.html', **data)

@app.route('/version', methods=['GET'])
def get_version():
  return jsonify({"version": app_config["version"]})

@app.route('/config', methods=['GET'])
def query_key():
  key = request.args.get('key')
  if not key:
    return jsonify(app_config), 200

  if key in app_config:
    return jsonify({key: app_config[key].value}), 200
  else:
    return jsonify({"error": "Key not found"}), 404

@app.route('/update', methods=['GET'])
def update_config():
  global app_config
  key = request.args.get('key')
  if not key:
    return jsonify({"error": "No key provided"}), 400

  if key not in app_config:
    return jsonify({"error": "Key not found"}), 500
    
  new_value = request.args.get("value")
  if new_value:
    app_config[key].value = new_value
    return jsonify({key: app_config[key].value}), 200
  return jsonify({"error": "No value provided"}), 400

@app.route('/start', methods=['GET'])
def start_timer():
  global app_config
  app_config["is_timer_running"].value = True

  #if the timer was already paused, need to account for the amount of time the timer
  #had already elapsed. Otherwise this would essentially reset the timer.
  app_config["start_timestamp"].value = timestamp() - app_config["timer_stop_uptime"].value

  return jsonify({"start_timestamp": app_config["start_timestamp"].value}), 200

@app.route('/stop', methods=['GET'])
def stop_timer():
  global app_config
  app_config["is_timer_running"].value = False
  app_config["stop_timestamp"].value = timestamp()

  #update the uptime each time we stop, so we know how much time had already elapsed at the time of stoppage
  app_config["timer_stop_uptime"].value = app_config["stop_timestamp"].value - app_config["start_timestamp"].value

  return jsonify({"stop_timestamp": app_config["stop_timestamp"].value}), 200

@app.route('/reset', methods=['GET'])
def reset_timer():
  global app_config
  time = request.args.get('time')
  if not time:
    app_config["start_timestamp"].value = timestamp()
    app_config["stop_timestamp"].value = timestamp()
  else:
    app_config["start_timestamp"].value = time
    app_config["stop_timestamp"].value = time

  app_config["timer_stop_uptime"].value = 0

  #always stop timer when reseting time
  app_config["is_timer_running"].value = False

  return jsonify({"start_timestamp": app_config["start_timestamp"].value}), 200

@app.route('/game_times', methods=['GET'])
def get_times():
  # Get how long the timer has been running
  if app_config["is_timer_running"].value == True:
    current_time = timestamp()
    uptime = int(current_time) - app_config["start_timestamp"].value
  else:
    current_time = app_config["stop_timestamp"].value
    uptime = int(current_time) - app_config["start_timestamp"].value

  # Initialize results dictionary
  times = {}
  times["uptime"] = uptime

  # Copy number of ends and time per end into dictionary to return
  times["num_ends"] = app_config["num_ends"].value
  times["time_per_end"] = app_config["time_per_end"].value

  # End number and percentage are always based on the uptime of the timer
  times["end_number"] = uptime // app_config["time_per_end"].value + 1
  times["end_percentage"] = uptime/app_config["time_per_end"].value - times["end_number"] + 1

  # Calculate the total time of the game, then figure out which time to split into
  # hours, minutes, and seconds depending on if we're counting down or up
  times["total_time"] = app_config["time_per_end"].value * app_config["num_ends"].value
  game_time = times["total_time"] - uptime if app_config["count_direction"].value < 0 else uptime
  
  # Determine if we're over time or not. If allow_overtime is false, then the over time flag will always be false
  times["is_overtime"] = uptime > times["total_time"] and app_config["allow_overtime"].value
  
  # If we don't allow overtime and the timer is done, directly call the stop function so timing stops
  # and set the time to 0 or total time, so it stays that way
  if uptime >= times["total_time"] and not app_config["allow_overtime"].value:
    stop_timer()
    game_time = 0 if app_config["count_direction"].value < 0 else times["total_time"]

  # If we're over time, then return how far over time we are
  if times["is_overtime"] and app_config["count_direction"].value < 0:
    game_time = game_time*-1

  # Divide the time into hours, minutes, seconds
  times["hours"] = game_time // 3600
  times["minutes"] = (game_time // 60) % 60
  times["seconds"] = game_time % 60
    
  return jsonify(times), 200

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--host", default="0.0.0.0", help="host IP to bind to")
  parser.add_argument("--port", default="5000", type=int, help="port for server to listen on")
  args = parser.parse_args()

  if USING_WAITRESS:
    waitress.serve(app, host='0.0.0.0', port=args.port)
  else:  
    app.run(port=args.port)
