# controller.py
from pynput import keyboard
from threading import Event

class StationController:
    def __init__(self):
        self.advance_event = Event()
        self.exit_event = Event()
        self.listener=keyboard.GlobalHotKeys({'0':self.request_advance,
                                              '-':self.request_exit})
        self.listener.start()
    
    def request_advance(self):
        self.advance_event.set()
    
    def request_exit(self):
        self.exit_event.set()
    
    def cleanup(self):

        keyboard.unhook_all()
