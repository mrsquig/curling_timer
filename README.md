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
|load_profile|GET| Updates the server configuration from a preset profile specified by `name`|
|shutdown|POST| Shuts down the server at the specified timestamp |

The route `/game_times` returns everything needed by a front-end application to display the status of the timer. It uses the following data structure:
| Key | Data type | Description |
|-----|-----------|-------------|
|times| dict | Computed values from server |
|config| dict | Current server configuartion |

The `times` dictionary uses the following data structure:
| Key | Data type | Description |
|-----|-----------|-------------|
|hours| int | Number of hours to display on the timer |
|minutes| int | Number of minutes to display on the timer |
|seconds| int | Number of seconds to display on the timer |
|end_number| int | Ideal end number if keeping to the specified pace |
|end_percentage| float | Percentage complete (out of 1) of the current end |
|overtime| bool | True if the game is past the time allotted for that game and overtime is allowed |
|total_time| int | Duration of the game in seconds |
|uptime| int | How long the timer has been running in seconds |

Preset profiles can be defined via a JSON file. The default file is named `server_profiles.json` and a customized file path can be
specified via the `--profiles` flag.

## Front end
An example PyGame front end is provided in `app.py` Simply run to start the front end.

```
python app.py
```

The host IP of the backend server can be specified with the `--host` flag, and the port with the `--port` flag. The defaults are `127.0.0.1` and `5000`.

Full-screen mode can be entered at run-time using the `--full-screen` flag (alternatively `-f`). If the server is not running, it will be started at run-time. The front end has the following key bindings:
|Key|Action|
|---|------|
|r| Reset timer|
|q| Quit front end|
|f| Toggle full screen|

### Customizing the styles of the front end

The colors of the front end elements can be customized by an optional style sheet file in JSON format. The style sheet is provided using the `--styles` or `-s` flag. The format of the file is an un-ordered list of key/value pairs. The value of each element is a three-element list of red, green, and blue values which define the color.

An example is as follows,

```
{
    "SCREEN_BG": [127, 127, 127],
    "BAR_FG": [127, 0, 200]
}
```

The colors should be defined using integer values of red, green, and blue. The integers must be between 0 and 255. The file can be changed while the timer is running to change the styles on-the-fly.

The following keys can be defined:

| Key | Description | Default value |
|-----|-------------|---------------|
|SCREEN_BG | Background color of the timer | (0, 0, 0) |
|BAR_FG | Progress bar foreground color | (40, 80, 160) |
|BAR_BG | Progress bar background color| (50, 50, 50) |
|TEXT | Main text color | (255, 255, 255)   |
|TEXT_END_MINUS1 | Text color used for the second to last end | (255, 204, 42) |
|TEXT_LASTEND | Text color used for the last end | (160, 80, 40) |
|OT | Overtime text color and progress bar foreground color | (160, 80, 40) |
