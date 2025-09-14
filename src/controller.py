# controller_gpio.py
from threading import Event, Thread
import logging
import time
import subprocess

logger = logging.getLogger(__name__)

class StationController:
    def __init__(self):
        self.advance_event = Event()
        self.exit_event = Event()
        self._button_states = {'advance': False, 'exit': False}
        self._setup_gpio_buttons()
    
    def _setup_gpio_buttons(self):
        """Setup physical GPIO buttons with debouncing"""
        try:
            import RPi.GPIO as GPIO
            
            # Use BCM numbering (GPIO numbers, not physical pin numbers)
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Button GPIO pins (customize these based on your wiring)
            self.advance_pin = 17    # GPIO17 (physical pin 11)
            self.exit_pin = 27       # GPIO27 (physical pin 13)
            
            # Setup pins as input with pull-up resistors
            GPIO.setup(self.advance_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.exit_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Add event detection with debouncing
            GPIO.add_event_detect(self.advance_pin, GPIO.FALLING, 
                                callback=self._advance_callback, bouncetime=300)
            GPIO.add_event_detect(self.exit_pin, GPIO.FALLING,
                                callback=self._exit_callback, bouncetime=300)
            
            logger.info("GPIO buttons setup successfully")
            logger.info(f"Advance button: GPIO{self.advance_pin}")
            logger.info(f"Exit button: GPIO{self.exit_pin}")
            
            # Start background thread to monitor buttons
            self._monitor_thread = Thread(target=self._monitor_buttons, daemon=True)
            self._monitor_thread.start()
            
        except ImportError:
            logger.warning("RPi.GPIO not available, falling back to terminal input")
            self._setup_terminal_fallback()
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            self._setup_terminal_fallback()
    
    def _advance_callback(self, channel):
        """Callback for advance button press"""
        if not self._button_states['advance']:
            self._button_states['advance'] = True
            self.request_advance()
            # Play button press sound feedback
            self._play_button_sound()
            logger.info("Advance button pressed")
    
    def _exit_callback(self, channel):
        """Callback for exit button press"""
        if not self._button_states['exit']:
            self._button_states['exit'] = True
            self.request_exit()
            # Play button press sound feedback
            self._play_button_sound()
            logger.info("Exit button pressed")
    
    def _monitor_buttons(self):
        """Monitor button states and reset after press"""
        while True:
            time.sleep(0.1)
            # Reset button states after short delay
            if self._button_states['advance']:
                time.sleep(0.5)  # Debounce period
                self._button_states['advance'] = False
            
            if self._button_states['exit']:
                time.sleep(0.5)  # Debounce period
                self._button_states['exit'] = False
    
    def _play_button_sound(self):
        """Provide audio feedback for button press"""
        try:
            subprocess.run(['aplay', '-q', 'button_press.wav'], 
                         timeout=1, capture_output=True)
        except:
            # Fallback to beep if audio file not available
            try:
                subprocess.run(['echo', '-e', '\a'], shell=False)
            except:
                pass
    
    def _setup_terminal_fallback(self):
        """Fallback to terminal input if GPIO fails"""
        def terminal_listener():
            while True:
                try:
                    user_input = input("\n[FALLBACK MODE] Press 0+Enter to advance, -+Enter to exit: ").strip()
                    if user_input == '0':
                        self.request_advance()
                        print("Advance command received")
                    elif user_input == '-':
                        self.request_exit()
                        print("Exit command received")
                except (EOFError, KeyboardInterrupt):
                    self.request_exit()
                    break
                except Exception as e:
                    logger.error(f"Terminal input error: {e}")
                    time.sleep(1)
        
        thread = Thread(target=terminal_listener, daemon=True)
        thread.start()
        logger.info("Terminal input fallback activated")
    
    def request_advance(self):
        self.advance_event.set()
    
    def request_exit(self):
        self.exit_event.set()
    
    def cleanup(self):
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
            logger.info("GPIO cleanup completed")
        except:
            pass
