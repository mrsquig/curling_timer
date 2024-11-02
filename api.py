from flask import Flask, jsonify, request
from datetime import datetime
import sys
from config import ConfigValue
import signal

def timestamp():
  return datetime.now().timestamp()

app = Flask(__name__)
app_config = {
    "version": ConfigValue(0.1),
    "time_per_end": ConfigValue(15*60, int),
    "num_ends": ConfigValue(8, int),
    "start_timestamp": ConfigValue(timestamp(), int)
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
  app_config["start_timestamp"].value = timestamp()
  return jsonify({"start_timestamp": app_config["start_timestamp"].value}), 200

@app.route('/game_times', methods=['GET'])
def get_times():
  current_time = timestamp()
  uptime = int(current_time) - app_config["start_timestamp"].value

  times = {}
  times["minutes"] = uptime // 60
  times["seconds"] = uptime % 60
  times["end_number"] = uptime // app_config["time_per_end"].value + 1
  times["end_percentage"] = uptime/app_config["time_per_end"].value - times["end_number"] + 1

  return jsonify(times), 200

@app.route('/shutdown', methods=['POST'])
def shutdown():
  shutdown_time = request.json.get("time")
  if shutdown_time < timestamp():    
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:      
      sys.exit(0)
    func()
  return jsonify({"message": "Server is shutting down..."})

if __name__ == '__main__':
  app.run(port=5000)
