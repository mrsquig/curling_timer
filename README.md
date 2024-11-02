# curling_timer
PyGame app for timing curling games

## Overview
The timer application uses a Flask RESTful API on the backend to setup the configuration of the timer settings and retrieve the current values of the timer. A PyGame front end display is provided. This project relies on the following third-party Python packages:

- Flask
- Requests
- PyGame


## Back end
The back end of the timer is written in `api.py`. To start the server:
```
python api.py
```

The following API routes are supported:

|Name|Request Type|Notes|
|----|------------|-----|
|version|GET|Returns the current version number.|
|config|GET|Returns the current value of the requested `key`, or the entire configuration if no key is provided.|
|update|GET|Updates the configuration `key` with the specified `value`.|
|reset|GET|Resets the start timestamp of the timer|
|game_times|GET| Get the current time state of the timer|
|shutdown|POST| Shuts down the server at the specified timestamp |


## Front end
An example PyGame front end is provided in `app.py` Simply run to start the front-end.

```
python app.py
```

If the server is not running, it will be started at run-time. The front-end has the following key bindings:
|Key|Action|
|---|------|
|r| Reset timer|
|q| Quit front end|
|f| Toggle full screen|