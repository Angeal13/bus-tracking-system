# audio_system.py
import pygame
import pyttsx3
import io
from gtts import gTTS
from gtts.tts import gTTSError
import time
from threading import Event
import requests
import socket

class AudioSystem:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_audio()
            cls._instance._cache = {}
            cls._instance.is_online = True
        return cls._instance
    
    def _init_audio(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 140)
        self.engine.setProperty('volume', 1.0)
        voices = self.engine.getProperty('voices')
        for voice in voices:
            # Set a default Spanish voice for pyttsx3 fallback
            if 'spanish' in voice.name.lower():
                self.engine.setProperty('voice', voice.id)
                break
        pygame.mixer.init()
    
    def play_audio(self, text: str, language: str, exit_event: Event, repetitions: int = 1):
        """Play text-to-speech audio with gTTS (online) or pyttsx3 (offline fallback)."""
        
        # Try to use gTTS with caching
        try:
            self._play_with_gtts(text, language, exit_event, repetitions)
            self.is_online = True
        except (gTTSError, requests.exceptions.ConnectionError, socket.timeout) as e:
            # Catch specific network-related errors to determine offline mode
            print(f"Audio playback error (gTTS): {e}. Falling back to pyttsx3.")
            self.is_online = False
            self._play_with_pyttsx3(text, exit_event, repetitions)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Falling back to pyttsx3.")
            self.is_online = False
            self._play_with_pyttsx3(text, exit_event, repetitions)
    
    def _play_with_gtts(self, text: str, language: str, exit_event: Event, repetitions: int):
        """Play audio using gTTS, with caching and repetitions."""
        cache_key = (text, language)
        if cache_key in self._cache:
            audio_data = self._cache[cache_key]
        else:
            tts = gTTS(text=text, lang=language)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            audio_data = fp.getvalue()
            self._cache[cache_key] = audio_data
        
        for i in range(repetitions):
            if exit_event.is_set():
                break
            
            fp = io.BytesIO(audio_data)
            fp.seek(0)
            pygame.mixer.music.load(fp, 'mp3')
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy() and not exit_event.is_set():
                pygame.time.Clock().tick(10)
            
            if i < repetitions - 1 and not exit_event.is_set():
                time.sleep(10)

    def _play_with_pyttsx3(self, text: str, exit_event: Event, repetitions: int):
        """Play audio using pyttsx3 as a fallback, with repetitions and pauses."""
        # Queue up all repetitions and pauses before playing
        for i in range(repetitions):
            if exit_event.is_set():
                break
            
            # Say the text
            self.engine.say(text)
            
            # Add a 10-second pause between repetitions
            if i < repetitions - 1:
                # This is a bit of a hack to simulate a delay, as pyttsx3 doesn't have a direct sleep command.
                # A very low rate for a brief silence creates a longer pause.
                original_rate = self.engine.getProperty('rate')
                self.engine.setProperty('rate', 1)
                self.engine.say("... ")
                self.engine.setProperty('rate', original_rate)
        
        self.engine.runAndWait()
    
    def cleanup(self):
        pygame.mixer.quit()
        self.engine.stop()