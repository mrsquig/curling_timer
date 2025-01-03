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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('curling_timer')
logger.setLevel(logging.INFO)

HOST_IP = None
SERVER_PORT = None
SERVER_PROCESS = None
CONFIG_UPDATE_TIME_LIMIT = 30
NUM_STONES_PER_END = 8

def timestamp():
  return datetime.datetime.now().timestamp()

class Color(Enum):
  SCREEN_BG = (0, 0, 0)
  TEXT = (255, 255, 255)  
  TEXT_END_MINUS1 = (255, 204, 42)
  TEXT_LASTEND = (160, 80, 40)
  BAR_FG = (40, 80, 160)
  BAR_BG = (50, 50, 50)
  OT = (160, 80, 40)

class IceClock:
  def __init__(self, width=1280, height=720, fullscreen=False):
    # Initialize Pygame
    pygame.init()

    # Setup the dimensions for window mode and full-screen mode
    # We need to do this before setting up the window so that we 
    # can get the accurate screen resolution.
    info = pygame.display.Info()
    self.fs_width = info.current_w
    self.fs_height = info.current_h    
    self.window_width = width
    self.window_height = height    

    # Set up the display -- start in window mode
    self.width = width if not fullscreen else self.fs_width
    self.height = height if not fullscreen else self.fs_height
    if not fullscreen:
      self.screen = pygame.display.set_mode((self.width, self.height))
    else:
      self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
    pygame.mouse.set_visible(not fullscreen)
    pygame.display.set_caption("Ice Clock")

    # Initialize UI elements
    self.init_UI()

    # Set the start time as the current time
    self.start_time = datetime.datetime.now()
    self.running = True
    self.fullscreen = fullscreen

  def init_UI(self):
    '''
    Initialize UI elements
    This should be called whenever the screen size changes
    '''
    # Set up the fonts
    #courier = pygame.font.match_font("couriernew", bold=True)
    jetbrains = os.path.join("ttf", "JetBrainsMono-Medium.ttf")
    self.fonts = {}
    self.fonts["timer"] = pygame.font.Font(jetbrains, 3*self.height // 16)
    self.fonts["last_end"] = pygame.font.Font(jetbrains, 2*self.height // 16)
    self.fonts["end"] = pygame.font.Font(jetbrains,  self.height // 2)
    self.fonts["end_progress_label"] = pygame.font.Font(jetbrains, self.height // 32)

    # Set up progress bar(s)
    self.bar_width = self.width // 8
    self.bar_height = 7*self.height // 8
    self.bar_x_offset = 13*self.width // 32
    bar_x = ((self.width - self.bar_width) // 2 - self.bar_x_offset,
             (self.width - self.bar_width) // 2 + self.bar_x_offset)
    self.bar_rects = [pygame.Rect(x, (self.height - self.bar_height)//2, 
                                self.bar_width, self.bar_height) for x in bar_x]

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
    return self._num_ends * self._time_per_end

  def update_time(self):
    '''
    Get the latest game time information through the REST API
    Setup the app object so that we can render the information
    '''

    try:
      response = requests.get('http://{:s}:{:s}/game_times'.format(HOST_IP, SERVER_PORT))
    except Exception as e:
      return f"Error: {e}"
    
    self._hours = response.json().get("hours")
    self._minutes = response.json().get("minutes")
    self._seconds = response.json().get("seconds")
    self._end_number = response.json().get("end_number")
    self._end_percentage = response.json().get("end_percentage")
    self._is_overtime = response.json().get("is_overtime")
    self._num_ends = response.json().get("num_ends")
    self._time_per_end = response.json().get("time_per_end")
    self._uptime = response.json().get("uptime")

  def get_text_color(self):
    if self._end_number < self._num_ends - 1:
      color = Color.TEXT.value
    elif self._end_number == self._num_ends - 1:
      color = Color.TEXT_END_MINUS1.value
    elif self._end_number == self._num_ends:
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

    is_last_end = self._end_number >= self._num_ends
    if is_last_end and not self._is_overtime:
      text = self.fonts["last_end"].render("LAST END", True, color)
    elif self._is_overtime:
      text = self.fonts["last_end"].render("OVERTIME", True, color)
    else:
      text = self.fonts["last_end"].render("", True, color)
  
    text_rect = text.get_rect(center=(self.center["x"], self.center["y"] + 6.5*self.height // 16))
    self.screen.blit(text, text_rect)
  
  def render_end_number(self):
    color = self.get_text_color()

    if not self._is_overtime:
      end_num = self._end_number if self._end_number < self._num_ends else self._num_ends
      text = self.fonts["end"].render("{:d}".format(end_num), True, color)
      text_rect = text.get_rect(center=(self.center["x"] - 2*self.width // 32, self.center["y"] - 3*self.height // 16))
      self.screen.blit(text, text_rect)
      
      text = self.fonts["timer"].render("/{:d}".format(self._num_ends), True, color)
      text_rect = text.get_rect(center=(self.center["x"] + 3*self.width // 32, self.center["y"] - 3*self.height // 16))
      self.screen.blit(text, text_rect)
    else:
      text = self.fonts["end"].render("OT", True, color)
      text_rect = text.get_rect(center=(self.center["x"], self.center["y"] - 3*self.height // 16))
      
      # Blink the "OT" text on for one second and off for one second when over time
      if not self._is_overtime or self._seconds % 2:
        self.screen.blit(text, text_rect)

  def render_end_progress_bar(self):
    for rect in self.bar_rects:
      pygame.draw.rect(self.screen, Color.BAR_BG.value, rect, border_radius = self.height//50)
    
    # Set the height of the progress bar
    # It is 1 - percentage so that the bar counts down instead of up
    # Round to an integer multiple of the number of stones per end
    percentage = int(NUM_STONES_PER_END*self._end_percentage)/NUM_STONES_PER_END
    filled_height = int(self.bar_height * (1 - percentage))
    if self._is_overtime:
      # Timer is expired and over time is allowed
      filled_height = int(self.bar_height)
    elif self._end_number > self._num_ends:
      # Timer is expired, but over time is not allowed
      filled_height = 0    

    for rect in self.bar_rects:
      filled_rect = pygame.Rect(rect.x, rect.y + self.bar_height - filled_height,
                                self.bar_width, filled_height)
      color = Color.BAR_FG.value if not self._is_overtime else Color.OT.value
      pygame.draw.rect(self.screen, color, filled_rect, border_radius = self.height//50)

      # Add dividers to progress bars for each stone
      for i in range(NUM_STONES_PER_END):
        stone_div = pygame.Rect(rect.x, rect.y + i*self.bar_height//8,
                           self.bar_width, self.height//100)
        pygame.draw.rect(self.screen, Color.SCREEN_BG.value, stone_div)

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

  def render(self):
    '''
    Render all UI elements to the PyGame window
    '''
    
    self.screen.fill(Color.SCREEN_BG.value)
    self.render_end_progress_bar()
    #self.render_end_progress_labels()
    self.render_timer()
    self.render_detail_text()
    self.render_end_number()

    # Update the display
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

  def run(self):
    # Main loop
    while self.running:
      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          self.teardown()
        if event.type == pygame.KEYDOWN:
          self.key_down_callback(event)

      self.update_time()
      self.render()
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
  args = parser.parse_args()

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
  clock = IceClock(fullscreen=args.full_screen)
  clock.run()
