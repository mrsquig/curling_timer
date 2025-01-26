from api import server_config
import app

import sys
from PIL import Image
from functools import wraps
import numpy as np
import unittest
import io
import os
import logging

logging.basicConfig()
logger = logging.getLogger("test_app")

GENERATE_GOLDENS = True
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(BASE_PATH, "app_tests")

def render_app(clock, end_num, end_percentage):
  img_io = io.BytesIO()

  total_time = server_config["time_per_end"].value * server_config["num_ends"].value
  elapsed = server_config["time_per_end"].value * (end_num - 1) + end_percentage * server_config["time_per_end"].value

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
    self.clock = app.IceClock(headless=True)
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
    if GENERATE_GOLDENS:
      with open(golden_path, "wb") as outfile:
        outfile.write(img_io.getvalue())
      self.assertEqual(True, True)
    self.assertImg(img_io, golden_path)

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
    end_percentage = 0.5
    img_io = render_app(self.clock, end_num, end_percentage)
    self.image_test(img_io, golden_path)

  @set_golden_path
  def test_last_end(self, golden_path=None):
    end_num = server_config["num_ends"].value
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
    self.clock._messages.append(("This message will be truncated because it is too long!", app.timestamp()))
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

if __name__ == '__main__':
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

  unittest.main()