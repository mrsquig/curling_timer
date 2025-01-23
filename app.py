import os
import sys
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

from enum import Enum
import collections
import subprocess
import datetime
import requests
import argparse
import pygame
import time
import logging
import json
import queue
import functools
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('curling_timer')
logger.setLevel(logging.INFO)

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

HOST_IP = None
SERVER_PORT = None
SERVER_PROCESS = None
CONFIG_UPDATE_TIME_LIMIT = 30
MESSAGE_TIME_LIMIT = 10
MESSAGE_CHR_SOFT_LIMIT = 10
MESSAGE_CHR_HARD_LIMIT = 20
MESSAGE_LINE_LIMIT = 3
Color = None

def timestamp():
  return datetime.datetime.now().timestamp()

def color_factory(colors=None):
  if colors is None:
    colors = {}

  default_styles = load_default_styles()
  remove_keys = []

  for key in colors:
    if not isinstance(colors[key], tuple) or len(colors[key]) != 3:
      logger.warning("Color values must be a 3-tuple of RGB values")
      logger.warning("Using default color values for {:s}".format(key))
      remove_keys.append(key)
      continue

    if not all(isinstance(v, int) for v in colors[key]):
      logger.warning("Color values must be integers")
      logger.warning("Using default color values for {:s}".format(key))
      remove_keys.append(key)
      continue

    if not all(0 <= v <= 255 for v in colors[key]):
      logger.warning("Color values must be between 0 and 255")
      logger.warning("Using default color values for {:s}".format(key))
      remove_keys.append(key)
      continue

  for key in remove_keys:
    colors.pop(key)

  class Color(Enum):
    SCREEN_BG = colors["SCREEN_BG"] if "SCREEN_BG" in colors else default_styles["colors"]["SCREEN_BG"]
    TEXT = colors["TEXT"] if "TEXT" in colors else default_styles["colors"]["TEXT"]
    TEXT_END_MINUS1 = colors["TEXT_END_MINUS1"] if "TEXT_END_MINUS1" in colors else default_styles["colors"]["TEXT_END_MINUS1"]
    TEXT_LASTEND = colors["TEXT_LASTEND"] if "TEXT_LASTEND" in colors else default_styles["colors"]["TEXT_LASTEND"]
    BAR_FG1 = colors["BAR_FG1"] if "BAR_FG1" in colors else default_styles["colors"]["BAR_FG1"]
    BAR_FG2 = colors["BAR_FG2"] if "BAR_FG2" in colors else default_styles["colors"]["BAR_FG2"]
    BAR_BG = colors["BAR_BG"] if "BAR_BG" in colors else default_styles["colors"]["BAR_BG"]
    BAR_BORDER = colors["BAR_BORDER"] if "BAR_BORDER" in colors else default_styles["colors"]["BAR_BORDER"]
    BAR_DIVIDER = colors["BAR_DIVIDER"] if "BAR_DIVIDER" in colors else default_styles["colors"]["BAR_DIVIDER"]
    OT = colors["OT"] if "OT" in colors else default_styles["colors"]["OT"]

  return Color

@functools.cache
def load_default_styles():
  # Read styles from the default file
  with open(os.path.join(BASE_PATH, "static", "app_styles", "default_styles.json"), "r") as f:
    default_styles = json.load(f)
    default_styles["colors"] = {k: tuple(v) for k,v in default_styles["colors"].items()}
  return default_styles

class IceClock:
  def __init__(self, width=1280, height=720, fullscreen=False, styles_path=None, styles=None, jestermode=False, headless=False):
    # Initialize Pygame
    pygame.init()
    pygame.mixer.init()

    # Initialize message stack
    self._messages = []

    # Setup the styles
    self.styles_path = styles_path
    self.styles = styles

    style_args_valid = (styles_path is not None or styles is not None) or (styles_path is None and styles is None)
    assert style_args_valid, "Either styles_path or styles must be provided, but not both."

    styles_folder_path = os.path.join(BASE_PATH, "static", "app_styles")
    if styles_path is not None:
      self.styles_path = styles_path if styles_folder_path in styles_path.lower() else os.path.join(styles_folder_path, styles_path)
    else:
      self.styles_path = os.path.join(styles_folder_path, "default_styles.json")

    self.last_read_styles = None
    self.update_styles()

    # Setup the dimensions for window mode and full-screen mode
    # We need to do this before setting up the window so that we
    # can get the accurate screen resolution.
    info = pygame.display.Info()
    self.headless = headless
    self.fs_width = info.current_w
    self.fs_height = info.current_h
    self.window_width = width
    self.window_height = height

    if not headless:
      # Set up the display -- start in window mode
      self.width = width if not fullscreen else self.fs_width
      self.height = height if not fullscreen else self.fs_height
      if not fullscreen:
        self.screen = pygame.display.set_mode((self.width, self.height))
      else:
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
      pygame.mouse.set_visible(not fullscreen)
      pygame.display.set_caption("Ice Clock")
    else:
      self.width = self.fs_width
      self.height = self.fs_height
      self.screen = pygame.Surface((self.width, self.height))

    # Initialize UI elements
    self.init_UI()

    # Set the start time as the current time
    self.start_time = datetime.datetime.now()
    self.running = True
    self.fullscreen = fullscreen
    self.jestermode = jestermode

    self._played_chime = False
    self.chime = pygame.mixer.Sound(os.path.join(BASE_PATH, "static", "sounds", "783755__chungus43a__montreal-metro-door-chime.wav"))

  def init_UI(self):
    '''
    Initialize UI elements
    This should be called whenever the screen size changes
    '''
    # Set up the fonts
    #courier = pygame.font.match_font("couriernew", bold=True)
    jetbrains = os.path.join(BASE_PATH, "ttf", "JetBrainsMono-Medium.ttf")
    self.fonts = {}
    self.fonts["timer"] = pygame.font.Font(jetbrains, 3*self.height // 16)
    self.fonts["last_end"] = pygame.font.Font(jetbrains, 2*self.height // 16)
    self.fonts["end"] = pygame.font.Font(jetbrains,  self.height // 2)
    self.fonts["end_progress_label"] = pygame.font.Font(jetbrains, self.height // 32)
    self.fonts["messages"] = pygame.font.Font(jetbrains, 3*self.height // 32)
    self.fonts["count_in"] = pygame.font.Font(jetbrains, 4*self.height // 16)

  def update_styles(self):
    global Color

    # Use the styles provided if they are not None
    if self.styles is not None:
      Color = color_factory(self.styles["colors"])
      return

    # Use default styles if no styles file is provided
    if self.styles_path is None:
      Color = color_factory({})
      return

    # Check if the styles file has been updated since last read
    if os.path.getmtime(self.styles_path) == self.last_read_styles:
      return

    # Read the styles from the file
    with open(self.styles_path, "r") as f:
      self.styles = json.load(f)
      self.styles["colors"] = {k: tuple(v) for k,v in self.styles["colors"].items()}
    self.last_read_styles = os.path.getmtime(self.styles_path)
    Color = color_factory(self.styles["colors"])

  @property
  def center(self):
    return {"x": self.width//2, "y": self.height//2}

  @property
  def config(self):
    try:
      response = requests.get('http://{:s}:{:s}/config'.format(HOST_IP, SERVER_PORT))
    except Exception as e:
      return f"Error: {e}"

    return response.json()

  @property
  def total_time(self):
    return self._total_time

  def update_time(self):
    '''
    Get the latest game time information through the REST API
    Setup the app object so that we can render the information
    '''

    try:
      response = requests.get('http://{:s}:{:s}/game_times'.format(HOST_IP, SERVER_PORT))
    except Exception as e:
      return f"Error: {e}"

    times = response.json().get("times")
    self._server_config = response.json().get("config")

    self._hours = times["hours"]
    self._minutes = times["minutes"]
    self._seconds = times["seconds"]
    self._end_number = times["end_number"]
    self._end_percentage = times["end_percentage"]
    self._is_overtime = times["is_overtime"]
    self._uptime = times["uptime"]
    self._total_time = times["total_time"]

  def get_text_color(self):
    if self._end_number < self._server_config["num_ends"] - 1:
      color = Color.TEXT.value
    elif self._end_number == self._server_config["num_ends"] - 1:
      color = Color.TEXT_END_MINUS1.value
    elif self._end_number >= self._server_config["num_ends"] and not self._server_config["allow_overtime"]:
      color = Color.TEXT_LASTEND.value
    else:
      color = Color.OT.value

    return color

  def render_club_logo(self):
    self.screen.blit(self.image, self.image_rect)

  def render_timer(self):
    color = self.get_text_color()

    text = self.fonts["timer"].render("{:02d}:{:02d}:{:02d}".format(self._hours, self._minutes, self._seconds), True, color)
    text_rect = text.get_rect(center=(self.center["x"], self.center["y"] + 4*self.height // 16))
    self.screen.blit(text, text_rect)

  def render_detail_text(self):
    color = self.get_text_color()

    is_last_end = self._end_number >= self._server_config["num_ends"]
    if is_last_end and not self._is_overtime:
      text = self.fonts["last_end"].render("LAST END", True, color)
    elif self._is_overtime:
      text = self.fonts["last_end"].render("OVERTIME", True, color)
    elif self._server_config["game_type"] == "bonspiel" and self._uptime >= self._server_config["time_to_chime"]:
      text = self.fonts["last_end"].render("FINISH END +1", True, color)
    else:
      text = self.fonts["last_end"].render("", True, color)

    if self._server_config["game_type"] != "bonspiel":
      text_rect = text.get_rect(center=(self.center["x"], self.center["y"] + 6.5*self.height // 16))
    else:
      text_rect = text.get_rect(center=(self.center["x"], self.center["y"] + 4*self.height // 16))
    self.screen.blit(text, text_rect)

  def render_count_in_warning(self):
    color = self.get_text_color()
    text = self.fonts["count_in"].render("Starting in", True, color)
    text_rect = text.get_rect(center=(self.center["x"], self.center["y"] - 3*self.height // 16))
    self.screen.blit(text, text_rect)

  def render_end_number(self):
    color = self.get_text_color()

    if not self._is_overtime:
      end_num = self._end_number if self._end_number < self._server_config["num_ends"] else self._server_config["num_ends"]
      text = self.fonts["end"].render("{:d}".format(end_num), True, color)
      text_rect = text.get_rect(center=(self.center["x"] - 2*self.width // 32, self.center["y"] - 3*self.height // 16))
      if self.jestermode:
        text = pygame.transform.flip(text, False, True)
      self.screen.blit(text, text_rect)

      text = self.fonts["timer"].render("/{:d}".format(self._server_config["num_ends"]), True, color)
      text_rect = text.get_rect(center=(self.center["x"] + 3*self.width // 32, self.center["y"] - 3*self.height // 16))
      if self.jestermode:
        text = pygame.transform.flip(text, False, True)
      self.screen.blit(text, text_rect)
    else:
      text = self.fonts["end"].render("OT", True, color)
      if self.jestermode:
        text = pygame.transform.flip(text, False, True)
      text_rect = text.get_rect(center=(self.center["x"], self.center["y"] - 3*self.height // 16))

      # Blink the "OT" text on for one second and off for one second when over time
      if not self._is_overtime or self._seconds % 2:
        if self.jestermode:
          text = pygame.transform.flip(text, False, True)
        self.screen.blit(text, text_rect)

  def render_end_progress_bar(self):
    stones_per_end = self._server_config["stones_per_end"]

    # Set up progress bar(s)
    self.bar_width = self.width // 8
    self.bar_height = 7*self.height // 8

    # Calculate the height for each stone section then update the progress bar height
    section_height = self.bar_height // stones_per_end
    self.bar_height = section_height * stones_per_end

    self.bar_x_offset = 13*self.width // 32
    bar_x = ((self.width - self.bar_width) // 2 - self.bar_x_offset,
             (self.width - self.bar_width) // 2 + self.bar_x_offset)

    # Draw the border first, then the background
    bar_bg_rects = [pygame.Rect(x, (self.height - self.bar_height)//2,
                      self.bar_width, self.bar_height) for x in bar_x]
    border = int(self.styles["parameters"]["bar_border_size"]/1000 * self.height)
    bar_borders = [pygame.Rect(bg.x-border, bg.y-border,
                                bg.width + 2*border, bg.height + 2*border) for bg in bar_bg_rects]
    for rect in bar_borders:
      pygame.draw.rect(self.screen, Color.BAR_BORDER.value, rect, border_radius=self.height // 50)

    for rect in bar_bg_rects:
      pygame.draw.rect(self.screen, Color.BAR_BG.value, rect, border_radius=self.height // 50)

    # Set the height of the progress bar
    # It is 1 - percentage so that the bar counts down instead of up
    # Round to an integer multiple of the number of stones per end
    percentage = int(stones_per_end * self._end_percentage) / stones_per_end
    filled_height = int(self.bar_height * (1-percentage))
    if self._is_overtime:
      # Timer is expired and overtime is allowed
      filled_height = int(self.bar_height)
    elif self._end_number > self._server_config["num_ends"]:
      # Timer is expired, but overtime is not allowed
      filled_height = 0

    # Two colors for the stones represents two teams and more contrast for better visibility
    color1 = Color.BAR_FG1.value if not self.jestermode else (255, 0, 0)
    color2 = Color.BAR_FG2.value if not self.jestermode else (0, 255, 0)

    for rect in bar_bg_rects:
      for i in range(stones_per_end):
        section_rect = pygame.Rect(rect.x, rect.y + self.bar_height - (i + 1) * section_height,
                                    self.bar_width, section_height)
        # Alternate colors for each stone section
        color_mod = 2*self.styles["parameters"]["color_every_nth"]
        color = color1 if i % color_mod < int(color_mod/2) else color2
        border_radius = self.height // 100 if i == 0 or i == stones_per_end - 1 else 0
        if (i + 1) * section_height <= filled_height:
          pygame.draw.rect(self.screen, color, section_rect, border_radius=border_radius)

        # Add dividers to progress bars for each stone
        if i:
          divider_height = int(self.styles["parameters"]["divider_size"]/1000 * self.height)
          stone_div = pygame.Rect(rect.x,
                                  rect.y + self.bar_height - (i) * section_height - divider_height//2,
                                  self.bar_width,
                                  divider_height)
          pygame.draw.rect(self.screen, Color.BAR_DIVIDER.value, stone_div)

  def render_end_progress_labels(self):
    color = self.get_text_color()
    text = (self.fonts["end_progress_label"].render("STONES", True, color),
            self.fonts["end_progress_label"].render("REMAINING", True, color))

    side_signs = (-1, 1)
    y_offsets = (self.center["y"] + 7.3*self.height // 16,
                 self.center["y"] + 7.7*self.height // 16)

    for sgn in side_signs:
      x_offset = (self.center["x"] + sgn*self.bar_x_offset)

      for txt, y_offset in zip(text, y_offsets):
        text_rect = txt.get_rect(center=(x_offset, y_offset))
        self.screen.blit(txt, text_rect)

  def render_messages(self):
    # Render messages from the server

    # Get the latest message and put it in the message queue
    msg = self._messages[-1]
    chr_queue = queue.Queue()
    for c in msg[0][0:MESSAGE_CHR_HARD_LIMIT*MESSAGE_LINE_LIMIT - 3]:
      chr_queue.put(c)

    # Split the message into lines
    output_lines = []
    line_buf = ""
    while not chr_queue.empty():
      c = chr_queue.get()

      if c == "\r":
        continue

      if c == "\n":
        output_lines.append(line_buf)
        line_buf = ""
        continue

      if len(line_buf) > MESSAGE_CHR_HARD_LIMIT:
        line_buf += "-"
        output_lines.append(line_buf)
        line_buf = c
        continue

      if len(line_buf) >= MESSAGE_CHR_SOFT_LIMIT and c == " ":
        output_lines.append(line_buf)
        line_buf = ""
        continue

      line_buf += c

    # Add the last line to the output. If the message was truncated, then
    # add an ellipsis to the end of the line
    if len(msg[0]) > MESSAGE_CHR_HARD_LIMIT*MESSAGE_LINE_LIMIT-3:
      line_buf += "..."

    output_lines.append(line_buf)
    Nlines = len(output_lines)

    # Render the message to the screen
    line_offset = self.height // 8
    color = self.get_text_color()
    for i, line in enumerate(output_lines):
      text = self.fonts["messages"].render(line, True, color)
      text_rect = text.get_rect(center=(self.center["x"], self.center["y"] + 4*self.height // 16 + (i-Nlines+2)*line_offset))
      self.screen.blit(text, text_rect)

    # Filter the messages to remove old messages
    self._messages = list(filter(lambda x: x[1] + MESSAGE_TIME_LIMIT > timestamp(), self._messages))

  def get_messages(self):
    '''
    Get the latest messages from the REST API
    '''

    try:
      response = requests.get('http://{:s}:{:s}/messages'.format(HOST_IP, SERVER_PORT))
    except Exception as e:
      return f"Error: {e}"

    messages = response.json().get("messages")
    self._server_config = response.json().get("config")

    for msg in messages:
      self._messages.append((msg, timestamp()))

  def handle_chime(self):
    # If in bonspiel mode and play the chime if it is time to do so and has not
    # been played yet
    if self._server_config["is_game_complete"] or not self._server_config["is_timer_running"]:
      self._played_chime = False
      return

    if (not self._played_chime and
        not self.headless and
        self._server_config["game_type"] == "bonspiel" and
        self._uptime >= self._server_config["time_to_chime"]):
      self.chime.play()
      self._played_chime = True

  def render(self):
    '''
    Render all UI elements to the PyGame window
    '''

    self.update_styles()
    self.screen.fill(Color.SCREEN_BG.value)
    if not self._server_config["count_in"]:
      self.render_end_progress_bar()
    #self.render_end_progress_labels()

    # If there are messages, render them and skip the timer
    if self._messages:
      self.render_messages()
    elif (self._server_config["game_type"] == "bonspiel" and
        self._uptime >= self._server_config["time_to_chime"]):
      # If bonspiel mode and the second to last end or later, then skip the timer
      pass
    else:
      self.render_timer()
    self.render_detail_text()

    if not self._server_config["count_in"]:
      self.render_end_number()
    else:
      self.render_count_in_warning()

    # Update the display
    if not self.headless:
      pygame.display.flip()

  def key_down_callback(self, event):
    '''
    Callback function to react to key down events
    '''

    if event.key == pygame.K_r:
      # R key -- reset the timer
      logger.debug("User requested reset")
      requests.get('http://{:s}:{:s}/reset'.format(HOST_IP, SERVER_PORT))
      return
    elif event.key == pygame.K_q:
      # Q key -- quit the front end
      logger.debug("User requested exit")
      try:
        # If the server was started with the front end, then lets try to shut it down too
        SERVER_PROCESS.terminate()
        logger.info("Shut down server successfully.")
      except:
        logger.warning("Could not terminate server process!")
      self.teardown()
      return
    elif event.key == pygame.K_f:
      # F key -- toggle fullscreen
      logger.debug("User requested fullscreen")
      pygame.mouse.set_visible(self.fullscreen)
      self.fullscreen = not self.fullscreen
      if self.fullscreen:
        self.width = self.fs_width
        self.height = self.fs_height
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
      else:
        self.width = self.window_width
        self.height = self.window_height
        self.screen = pygame.display.set_mode((self.width, self.height))
      self.init_UI()

  def render_to_image(self, output):
    if (self._hours is None or self._minutes is None or self._seconds is None
        or self._end_number is None or self._end_percentage is None or self._is_overtime is None):
      self._hours = 1
      self._minutes = 7
      self._seconds = 30
      self._end_number = 1
      self._end_percentage = 0.5
      self._is_overtime = False
    self.render()

    pygame.image.save(self.screen, output, "PNG")
    output.seek(0)

  def run(self):
    # Main loop
    while self.running:
      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          self.teardown()
        if event.type == pygame.KEYDOWN:
          self.key_down_callback(event)

      # If there are messages, then we can skip updating the time
      if not self._messages:
        self.update_time()

      # Get the latest messages from the server and render all UI elements
      self.handle_chime()
      self.get_messages()
      self.render()

      # If there are messages, then update the UI more frequently. Otherwise,
      # update once per second.
      if not self._messages:
        time.sleep(1)

  def teardown(self):
    '''
    Exit the front end and cleanup as needed.
    '''
    pygame.quit()
    sys.exit()

def check_server():
  try:
    response = requests.get('http://{:s}:{:s}/version'.format(HOST_IP, SERVER_PORT))
    return response.status_code == 200
  except requests.ConnectionError:
    return False

def start_server(host="127.0.0.1", port="5000"):
  return subprocess.Popen([sys.executable, 'api.py', "--host", host, "--port", port])

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--host", default="127.0.0.1", help="host IP of backend server")
  parser.add_argument("--port", default="5000", help="port that backend server is listening on")
  parser.add_argument("--full-screen", "-f", action="store_true", default=False, help="launch in full screen mode")
  parser.add_argument("--styles", "-s", default=None, help="path to JSON file with color styles")
  parser.add_argument("-j", "--jester", action="store_true", help=argparse.SUPPRESS, required=False)
  args = parser.parse_args()

  # Set the variable based on the argument
  HOST_IP = args.host
  SERVER_PORT = args.port

  # Start the server if it is not already running
  if not check_server():
    logger.info("Could not find backend server. Attempting to start backend server...")
    SERVER_PROCESS = start_server(host=HOST_IP, port=SERVER_PORT)
    if check_server():
      logger.info("Started backend server successfully -- PID: {:d}".format(SERVER_PROCESS.pid))
    else:
      logger.error("Could not start backend server!")
      sys.exit(1)

  # Start the front end
  clock = IceClock(fullscreen=args.full_screen, styles_path=args.styles)
  clock.run()
