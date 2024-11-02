import pygame
import sys
import time
import datetime
from enum import Enum
import subprocess
import requests

class Color(Enum):
  SCREEN_BG = (0, 0, 0)
  TEXT = (255, 255, 255)
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

  def update_time(self):
    '''
    Get the latest game time information through the REST API
    Setup the app object so that we can render the information
    '''

    try:
      response = requests.get('http://127.0.0.1:5000/game_times')
    except Exception as e:
      return f"Error: {e}"
    
    self._minutes = response.json().get("minutes")
    self._seconds = response.json().get("seconds")
    self._end_number = response.json().get("end_number")
    self._end_percentage = response.json().get("end_percentage")

  def render_club_logo(self):
    self.screen.blit(self.image, self.image_rect)

  def render_timer(self, over_time=False):
    color = Color.TEXT.value if not over_time else Color.OT.value
    text = self.timer_font.render("{:02d}:{:02d}".format(self._minutes, self._seconds), True, color)
    text_rect = text.get_rect(center=(self.width // 2, self.height // 2 + 64))
    self.screen.blit(text, text_rect)

  def render_end_number(self, over_time=False):
    if not over_time:
      text = self.end_font.render("{:d}".format(self._end_number), True, Color.TEXT.value)
    else:
      text = self.end_font.render("OT", True, Color.OT.value)

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
      requests.get('http://127.0.0.1:5000/reset')
      return
    elif event.key == pygame.K_q:
      # Q key -- quit the front end
      pygame.quit()
      return
    elif event.key == pygame.K_f:
      # F key -- toggle full screen
      self.fullscreen = not self.fullscreen      
      if self.fullscreen:
        self.width = self.fs_width
        self.height = self.fs_height
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
      else:
        self.width = self.window_width
        self.height = self.window_height
        self.screen = pygame.display.set_mode((self.width, self.height))
      self.init_display()

  def run(self):
    # Main loop
    while self.running:
      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          stop_server()
          pygame.quit()          
          sys.exit()
        if event.type == pygame.KEYDOWN:
          self.key_down_callback(event)

      self.update_time()

      over_time = self._end_number > get_config("num_ends")
      self.render(over_time)
      time.sleep(1)

def check_server():  
  try:
    response = requests.get('http://127.0.0.1:5000/version')
    return response.status_code == 200
  except requests.ConnectionError:
    return False

def start_server():
  subprocess.Popen(['python', 'api.py'])

def stop_server():
  response = requests.post("http://127.0.0.1:5000/shutdown", json={"time": 0})

def get_config(key):
  try:
    response = requests.get('http://127.0.0.1:5000/config?key={:s}'.format(key))
  except Exception as e:
    return f"Error: {e}"

  return response.json().get(key)

if __name__ == "__main__":
  # Start the server if it is not already running
  if not check_server():
    start_server()

  # Start the front end
  clock = IceClock()
  clock.run()