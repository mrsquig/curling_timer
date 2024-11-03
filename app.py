import os
import sys
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

from enum import Enum
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

class Color(Enum):
  SCREEN_BG = (0, 0, 0)
  TEXT = (255, 255, 255)  
  TEXT_END_MINUS1 = (255, 204, 42)
  TEXT_LASTEND = (160, 80, 40)
  BAR_FG = (40, 80, 160)
  BAR_BG = (50, 50, 50)
  OT = (160, 80, 40)

class IceClock:
  def __init__(self, width=1024, height=512):
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
    self.width = width
    self.height = height
    self.screen = pygame.display.set_mode((self.width, self.height))
    pygame.display.set_caption("Ice Clock")

    # Initialize UI elements
    self.init_UI()

    # Set the start time as the current time
    self.start_time = datetime.datetime.now()
    self.running = True
    self.fullscreen = False

  def init_UI(self):
    '''
    Initialize UI elements
    This should be called whenever the screen size changes
    '''
    # Set up the fonts
    self.timer_font = pygame.font.Font(None, 128)
    self.end_font = pygame.font.Font(None, 256)

    # Set up club logo
    self.original_image = pygame.image.load("./logo.png")
    self.image = pygame.transform.scale(self.original_image, (256, 256))
    self.image_rect = self.image.get_rect(center=(self.width // 2 - 256 - 50, self.height // 2))

    # Set up progress bar
    self.bar_width = 100
    self.bar_height = 256
    self.bar_rect = pygame.Rect(self.width // 2 + 256, 
                                (self.height - self.bar_height)//2, 
                                self.bar_width, 
                                self.bar_height)

  @property
  def num_ends(self):
    return get_config("num_ends")

  def update_time(self):
    '''
    Get the latest game time information through the REST API
    Setup the app object so that we can render the information
    '''

    try:
      response = requests.get('http://{:s}:{:s}/game_times'.format(HOST_IP, SERVER_PORT))
    except Exception as e:
      return f"Error: {e}"
    
    self._minutes = response.json().get("minutes")
    self._seconds = response.json().get("seconds")
    self._end_number = response.json().get("end_number")
    self._end_percentage = response.json().get("end_percentage")

  def render_club_logo(self):
    self.screen.blit(self.image, self.image_rect)

  def render_timer(self, over_time=False):
    if self._end_number < self.num_ends - 1:
      color = Color.TEXT.value
    elif self._end_number == self.num_ends - 1:
      color = Color.TEXT_END_MINUS1.value
    elif self._end_number == self.num_ends:
      color = Color.TEXT_LASTEND.value
    else:
      color = Color.OT.value

    text = self.timer_font.render("{:02d}:{:02d}".format(self._minutes, self._seconds), True, color)
    text_rect = text.get_rect(center=(self.width // 2, self.height // 2 + 64))

    # Always display the timer during the game and blink the timer on for one second
    # and off for one second when over time
    if not over_time or self._seconds % 2:
      self.screen.blit(text, text_rect)

  def render_end_number(self, over_time=False):
    if self._end_number < self.num_ends - 1:
      color = Color.TEXT.value
    elif self._end_number == self.num_ends - 1:
      color = Color.TEXT_END_MINUS1.value
    elif self._end_number == self.num_ends:
      color = Color.TEXT_LASTEND.value
    else:
      color = Color.OT.value

    if not over_time:
      text = self.end_font.render("{:d}".format(self._end_number), True, color)
    else:
      text = self.end_font.render("OT", True, color)

    text_rect = text.get_rect(center=(self.width // 2, self.height // 2 - 64))
    self.screen.blit(text, text_rect)

  def render_end_progress_bar(self, over_time=False):
    pygame.draw.rect(self.screen, Color.BAR_BG.value, self.bar_rect)
    
    if over_time:
      filled_height = int(self.bar_height)
    else:
      # It is 1 - percentage so that the bar counts down instead of up    
      filled_height = int(self.bar_height * (1 - self._end_percentage))

    filled_rect = pygame.Rect(self.bar_rect.x, self.bar_rect.y + self.bar_height - filled_height,
                              self.bar_width, filled_height)
    color = Color.BAR_FG.value if not over_time else Color.OT.value
    pygame.draw.rect(self.screen, color, filled_rect)

  def render(self, over_time=False):
    '''
    Render all UI elements to the PyGame window
    The variable over_time designates if the current game is over time, which allows
    UI elements to react to this.
    '''
    
    self.screen.fill(Color.SCREEN_BG.value)
    self.render_club_logo()
    self.render_end_progress_bar(over_time)
    self.render_timer(over_time)
    self.render_end_number(over_time)

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
      over_time = self._end_number > self.num_ends
      self.render(over_time)
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

def get_config(key):
  try:
    response = requests.get('http://{:s}:{:s}/config?key={:s}'.format(HOST_IP, SERVER_PORT, key))
  except Exception as e:
    return f"Error: {e}"

  return response.json().get(key)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--host", default="127.0.0.1", help="host IP of backend server")
  parser.add_argument("--port", default="5000", help="port that backend server is listening on")
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
  clock = IceClock()
  clock.run()
