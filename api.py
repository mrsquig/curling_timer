from flask import Flask, jsonify, request
from datetime import datetime
from config import ConfigValue
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
    "count_direction": ConfigValue(-1, int),
}

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
    
  new_value = request.args.get("value")
  if new_value:
    app_config[key].value = new_value
    return jsonify({key: app_config[key].value}), 200
  return jsonify({"error": "No value provided"}), 400

@app.route('/reset', methods=['GET'])
def reset_timer():
  global app_config
  time = request.args.get('time')
  if not time:
    app_config["start_timestamp"].value = timestamp()
  else:
    app_config["start_timestamp"].value = time

  return jsonify({"start_timestamp": app_config["start_timestamp"].value}), 200

@app.route('/game_times', methods=['GET'])
def get_times():
  # Get how long the timer has been running
  current_time = timestamp()
  uptime = int(current_time) - app_config["start_timestamp"].value

  # Initialize results dictionary
  times = {}

  # End number and percentage are always based on the uptime of the timer
  times["end_number"] = uptime // app_config["time_per_end"].value + 1
  times["end_percentage"] = uptime/app_config["time_per_end"].value - times["end_number"] + 1

  # Calculate the total time of the game, then figure out which time to split into
  # hours, minutes, and seconds depending on if we're counting down or up
  times["total_time"] = app_config["time_per_end"].value * app_config["num_ends"].value
  game_time = times["total_time"] - uptime if app_config["count_direction"].value < 0 else uptime

  # If we're over time, then return how far over time we are
  times["overtime"] = uptime > times["total_time"]
  if times["overtime"] and app_config["count_direction"].value < 0:
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
