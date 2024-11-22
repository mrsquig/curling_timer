# curling_timer
PyGame app for timing curling games

## Overview
The timer application uses a Flask RESTful API on the backend to set up the configuration of the timer settings and retrieve the current values of the timer. A PyGame front-end display is provided. This project relies on the following third-party Python packages:

- Flask
- Requests
- PyGame
- Waitress (optional)


## Back end
The back end of the timer is written in `api.py`. To start the server:
```
python api.py
```

The server will start with Waitress if installed, or the Flask development server otherwise. A simple web utility is provided at the root of the server for controlling the configuration of the timer. The host to bind to can be specified with the `--host` flag, and the port with the `--port` flag. The defaults are `0.0.0.0` and `5000`. The value of `0.0.0.0` for the host IP allows any device on the network to communicate with the server.

The following API routes are supported:

|Name|Request Type|Notes|
|----|------------|-----|
|version|GET|Returns the current version number.|
|config|GET|Returns the current value of the requested `key`, or the entire configuration if no key is provided.|
|update|GET|Updates the configuration `key` with the specified `value`.|
|reset|GET|Resets the start timestamp of the timer|
|game_times|GET| Get the current time state of the timer|
|shutdown|POST| Shuts down the server at the specified timestamp |

The route `/game_times` returns everything needed by a front-end application to display the status of the timer. It uses the following data structure:
| Key | Data type | Description |
|-----|-----------|-------------|
|hours| int | Number of hours to display on the timer |
|minutes| int | Number of minutes to display on the timer |
|seconds| int | Number of seconds to display on the timer |
|end_number| int | Ideal end number if keeping to the specified pace |
|end_percentage| float | Percentage complete (out of 1) of the current end |
|overtime| bool | True if the game is past the time allotted for that game and overtime is allowed |
|time_per_end| int | Current setting of time per end in seconds |
|total_time| int | Duration of the game in seconds |
|uptime| int | How long the timer has been running in seconds |


## Front end
An example PyGame front end is provided in `app.py` Simply run to start the front end.

```
python app.py
```

The host IP of the backend server can be specified with the `--host` flag, and the port with the `--port` flag. The defaults are `127.0.0.1` and `5000`.

If the server is not running, it will be started at run-time. The front end has the following key bindings:
|Key|Action|
|---|------|
|r| Reset timer|
|q| Quit front end|
|f| Toggle full screen|