# controller.py
import keyboard
from threading import Event

class StationController:
    def __init__(self):
        self.advance_event = Event()
        self.exit_event = Event()
        keyboard.add_hotkey('0', self.request_advance)
        keyboard.add_hotkey('-', self.request_exit)
    
    def request_advance(self):
        self.advance_event.set()
    
    def request_exit(self):
        self.exit_event.set()
    
    def cleanup(self):
        keyboard.unhook_all()