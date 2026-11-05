from api import server_config
import app

import sys
from PIL import Image
from functools import wraps
import numpy as np
import unittest
from unittest import mock
import io
import os
import logging

logging.basicConfig()
logger = logging.getLogger("test_app")

GENERATE_GOLDENS = "-g" in sys.argv or "--golden" in sys.argv
# There are command line arguments defined by unittest. Intercept the arguments
# to check if there is a "--golden" or "-g" flag, then remove it from the list
# before the rest of the arguments are parsed
if GENERATE_GOLDENS:
  for idx in range(len(sys.argv)):
    if "-g" == sys.argv[idx] or "--golden" == sys.argv[idx]:
      break
  sys.argv.pop(idx)
  logger.info("Generating goldens -- tests are not being run!")

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(BASE_PATH, "app_tests")

def render_app(clock, end_num, end_percentage):
  img_io = io.BytesIO()

  clock._total_time = clock._server_config["num_ends"] * clock._server_config["time_per_end"]
  if not clock._server_config["count_in"] and not clock._server_config["game_type"] == "bonspiel":
    clock._end_number = end_num
    clock._uptime = clock._server_config["time_per_end"] * (end_num - 1) + end_percentage * clock._server_config["time_per_end"]

    num_ends = clock._server_config["num_ends"]
    time_per_end = clock._server_config["time_per_end"]
    total_time = clock.cutoff_times[clock.warning_level]
    elapsed = clock._uptime
  elif clock._server_config["game_type"] == "bonspiel":
    total_time = clock._server_config["time_per_end"] * clock._server_config["num_ends"]
    elapsed = clock._server_config["time_per_end"] * (end_num - 1) + end_percentage * clock._server_config["time_per_end"]
  else:
    total_time = clock._server_config["count_in"]
    elapsed = 0

  clock._uptime = elapsed
  clock._hours = int((total_time-elapsed) // 3600)
  clock._minutes = int(((total_time-elapsed) // 60) % 60)
  clock._seconds = int((total_time-elapsed) % 60)
  clock._end_number = end_num
  clock._end_percentage = end_percentage
  clock._is_overtime = False
  clock.render_to_image(img_io)
  img_io.seek(0)
  return img_io

def set_golden_path(func):
  @wraps(func)
  def wrapper(*args, **kwargs):
    golden_path = os.path.join(GOLDEN_DIR, "{:s}.png".format(func.__name__))
    return func(golden_path=golden_path, *args, **kwargs)
  return wrapper

class TestIceClock(unittest.TestCase):
  def setUp(self):
    self.clock = app.IceClock(headless=True, styles_path="default_styles.json")
    self.clock._server_config = {k: v.value for k,v in server_config.items()}

    if GENERATE_GOLDENS and not os.path.isdir(GOLDEN_DIR):
      os.mkdir(GOLDEN_DIR)

  def assertImg(self, img_io, golden_path):
    golden = Image.open(golden_path)
    current = Image.open(img_io)
    diff = np.abs(np.array(golden) - np.array(current))

    for channel in range(diff.shape[2]):
      self.assertTrue(np.all(diff[:,:,channel] <= 1))

  def image_test(self, img_io, golden_path):
    if GENERATE_GOLDENS or not os.path.isfile(golden_path):
      with open(golden_path, "wb") as outfile:
        outfile.write(img_io.getvalue())
      self.assertEqual(True, True)

    try:
      self.assertImg(img_io, golden_path)
    except AssertionError:
      with open(os.path.splitext(golden_path)[0]+"_fail.png", "wb") as outfile:
        outfile.write(img_io.getvalue())
      self.assertEqual(True, False)

  @set_golden_path
  def test_first_end(self, golden_path=None):
    end_num = 1
    end_percentage = 0.0

    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_styles(self, golden_path=None):
    self.clock.__init__(self.clock, styles_path="rcc_styles.json",
                        fullscreen=self.clock.fullscreen,
                        jestermode=self.clock.jestermode,
                        headless=self.clock.headless)
    end_num = 1
    end_percentage = 0.0
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_second_to_last(self, golden_path=None):
    end_num = server_config["num_ends"].value - 1
    end_percentage = 0.3
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_last_end(self, golden_path=None):
    end_num = server_config["num_ends"].value
    end_percentage = 0.3
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_warning1(self, golden_path=None):
    end_num = server_config["num_ends"].value - 1
    end_percentage = 0.5
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_warning2(self, golden_path=None):
    end_num = server_config["num_ends"].value
    end_percentage = 0.5
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_warning1_6end(self, golden_path=None):
    self.clock._server_config["num_ends"] = 6
    end_num =  self.clock._server_config["num_ends"] - 1
    end_percentage = 0.5
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_short_message(self, golden_path=None):
    end_num = 2
    end_percentage = 0.5
    self.clock._messages.append(("Hello World!", app.timestamp()))
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_long_message(self, golden_path=None):
    end_num = 2
    end_percentage = 0.5
    self.clock._messages.append(("This message will be truncated because it is too long! It is really very long. Who made this message so long?", app.timestamp()))
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_spiel_after_chime(self, golden_path=None):
    end_num = 7
    end_percentage = 0.75
    self.clock._server_config["game_type"] = "bonspiel"
    self.clock._server_config["time_to_chime"] = 6000
    self.clock._uptime = self.clock._server_config["time_per_end"] * (end_num-1+end_percentage)
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_spiel_before_chime(self, golden_path=None):
    end_num = 7
    end_percentage = 0.5
    self.clock._server_config["game_type"] = "bonspiel"
    self.clock._server_config["time_to_chime"] = 6000
    self.clock._uptime = self.clock._server_config["time_per_end"] * (end_num-1+end_percentage)
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_spiel_after_game(self, golden_path=None):
    end_num = 9
    end_percentage = 0.0
    self.clock._server_config["game_type"] = "bonspiel"
    self.clock._server_config["time_to_chime"] = 6000
    self.clock._server_config["is_game_complete"] = True
    self.clock._uptime = self.clock._server_config["time_per_end"] * (end_num-1+end_percentage)
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_count_in(self, golden_path=None):
    end_num = 1
    end_percentage = 0.0
    self.clock._server_config["count_in"] = 10
    self.clock._uptime = self.clock._server_config["time_per_end"] * (end_num-1+end_percentage)
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_doubles_5stones(self, golden_path=None):
    end_num = 1
    end_percentage = 0.0
    self.clock._server_config["stones_per_end"] = 5
    self.clock._uptime = self.clock._server_config["time_per_end"] * (end_num-1+end_percentage)
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  def _screen_styles(self, screen_bg, extra_colors=None):
    colors = {"SCREEN_BG": screen_bg}
    if extra_colors:
      colors.update(extra_colors)
    return {
      "colors": colors,
      "parameters": {
        "color_every_nth": 2,
        "divider_size": 5,
        "bar_border_size": 5
      }
    }

  def _corner_color(self, styles, end_num, end_percentage, allow_overtime=False):
    self.clock.__init__(styles=styles, headless=True)
    self.clock._server_config = {k: v.value for k, v in server_config.items()}
    self.clock._server_config["allow_overtime"] = allow_overtime
    self.clock._server_config["game_type"] = "league"
    self.clock._server_config["count_in"] = 0
    img_io = render_app(self.clock, end_num, end_percentage)
    return Image.open(img_io).getpixel((0, 0))[:3]

  def test_warning_background_defaults_to_screen_bg(self):
    screen_bg = (12, 34, 56)
    styles = self._screen_styles(screen_bg)
    num_ends = server_config["num_ends"].value
    self.assertEqual(screen_bg, self._corner_color(styles, num_ends - 1, 0.5))
    self.assertEqual(1, self.clock.warning_level)
    self.assertEqual(screen_bg, self._corner_color(styles, num_ends, 0.5))
    self.assertEqual(2, self.clock.warning_level)
    self.assertEqual(screen_bg, self._corner_color(styles, num_ends, 0.5, allow_overtime=True))
    self.assertEqual(-1, self.clock.warning_level)

  def test_warning_background_uses_style_colors(self):
    styles = self._screen_styles((1, 2, 3), {
      "SCREEN_BG_WARNING_1": (10, 0, 0),
      "SCREEN_BG_WARNING_2": (0, 10, 0),
      "SCREEN_BG_OT": (0, 0, 10)
    })
    num_ends = server_config["num_ends"].value
    self.assertEqual((10, 0, 0), self._corner_color(styles, num_ends - 1, 0.5))
    self.assertEqual((0, 10, 0), self._corner_color(styles, num_ends, 0.5))
    self.assertEqual((0, 0, 10), self._corner_color(styles, num_ends, 0.5, allow_overtime=True))

  def test_overtime_text_uses_text_ot(self):
    num_ends = server_config["num_ends"].value
    styles = self._screen_styles((0, 0, 0), {"TEXT_OT": (1, 2, 3), "OT": (9, 9, 9)})
    self._corner_color(styles, num_ends, 0.5, allow_overtime=True)
    self.assertEqual(-1, self.clock.warning_level)
    self.assertEqual((1, 2, 3), self.clock.get_text_color())

  def test_overtime_text_falls_back_to_ot(self):
    num_ends = server_config["num_ends"].value
    styles = self._screen_styles((0, 0, 0), {"OT": (4, 5, 6)})
    self._corner_color(styles, num_ends, 0.5, allow_overtime=True)
    self.assertEqual(-1, self.clock.warning_level)
    self.assertEqual((4, 5, 6), self.clock.get_text_color())

  def test_update_time_bonspiel_uses_api_clock(self):
    game_times = {
      "times": {
        "end_number": 9,
        "end_percentage": 0.1,
        "is_overtime": True,
        "uptime": 7000,
        "total_time": 6000,
        "hours": 1,
        "minutes": 6,
        "seconds": 40,
      },
      "config": {
        "game_type": "bonspiel",
        "num_ends": 8,
        "time_per_end": 900,
        "allow_overtime": True,
        "time_to_chime": 6000,
        "count_in": 0,
        "is_game_complete": False,
        "is_timer_running": True,
        "stones_per_end": 8,
      },
    }
    # /config serializes each ConfigValue as {"value": ...}, unlike /game_times.
    raw_config = {key: {"value": value} for key, value in game_times["config"].items()}

    def fake_get(url, *args, **kwargs):
      class Response:
        def __init__(self, payload):
          self._payload = payload
        def json(self):
          return self._payload
      if url.endswith("/config"):
        return Response(raw_config)
      return Response(game_times)

    app.HOST_IP = "127.0.0.1"
    app.SERVER_PORT = "5000"
    with mock.patch("app.requests.get", side_effect=fake_get):
      self.clock.update_time()

    self.assertEqual(1, self.clock._hours)
    self.assertEqual(6, self.clock._minutes)
    self.assertEqual(40, self.clock._seconds)
    self.assertEqual(-1, self.clock.warning_level)

  @set_golden_path
  def test_doubles_10stones(self, golden_path=None):
    end_num = 1
    end_percentage = 0.0
    self.clock._server_config["stones_per_end"] = 10
    self.clock._uptime = self.clock._server_config["time_per_end"] * (end_num-1+end_percentage)
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

if __name__ == '__main__':
  unittest.main()