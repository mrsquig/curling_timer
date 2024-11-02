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

class IceClock:
  def __init__(self, width=1024, height=512):
    # Initialize Pygame
    pygame.init()

    # Set up the display
    self.width = width
    self.height = height
    self.screen = pygame.display.set_mode((self.width, self.height))
    pygame.display.set_caption("Ice Clock")

    # Set up the fonts
    self.timer_font = pygame.font.Font(None, 128)
    self.end_font = pygame.font.Font(None, 256)

    # Set up club logo
    self.image = pygame.image.load("./logo.png")
    self.image = pygame.transform.scale(self.image, (256, 256))
    self.image_rect = self.image.get_rect(center=(self.width // 2 - 256 - 50, self.height // 2))

    # Set up progress bar
    self.bar_width = 100
    self.bar_height = 256
    self.bar_rect = pygame.Rect(self.width - 256, 
                                (self.height - self.bar_height)//2, 
                                self.bar_width, 
                                self.bar_height)

    # Set the start time as the current time
    self.start_time = datetime.datetime.now()
    self.running = True

  def update_time(self):    
    try:
      response = requests.get('http://127.0.0.1:5000/game_times')
    except Exception as e:
      return f"Error: {e}"
    
    self._minutes = response.json().get("minutes")
    self._seconds = response.json().get("seconds")
    self._end_number = response.json().get("end_number")
    self._end_percentage = 1 - response.json().get("end_percentage")

  def render_logo(self):
    self.screen.blit(self.image, self.image_rect)

  def render_timer(self):    
    text = self.timer_font.render("{:02d}:{:02d}".format(self._minutes, self._seconds), True, Color.TEXT.value)
    text_rect = text.get_rect(center=(self.width // 2, self.height // 2 + 64))
    self.screen.blit(text, text_rect)

  def render_end(self):
    text = self.end_font.render("{:d}".format(self._end_number), True, Color.TEXT.value)
    text_rect = text.get_rect(center=(self.width // 2, self.height // 2 - 64))
    self.screen.blit(text, text_rect)

  def render_progress(self):    
    pygame.draw.rect(self.screen, Color.BAR_BG.value, self.bar_rect)
    filled_height = int(self.bar_height * self._end_percentage)
    filled_rect = pygame.Rect(self.bar_rect.x, self.bar_rect.y + self.bar_height - filled_height,
                              self.bar_width, filled_height)
    pygame.draw.rect(self.screen, Color.BAR_FG.value, filled_rect)

  def render(self):    
    self.render_logo()
    self.render_progress()
    self.render_timer()
    self.render_end()

    # Update the display
    pygame.display.flip()

  def run(self):
    # Main loop
    while self.running:
      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          stop_server()
          pygame.quit()          
          sys.exit()

      self.screen.fill(Color.SCREEN_BG.value)
      self.update_time()

      if self._end_number <= get_config("num_ends"):
        self.render()
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
  if not check_server():
    start_server()

  clock = IceClock()
  clock.run()