# audio_utils.py
import subprocess
import logging
import os

logger = logging.getLogger(__name__)

class AudioConfig:
    @staticmethod
    def ensure_audio_output_jack():
        """Ensure audio outputs through 3.5mm jack and set volume"""
        try:
            # Force audio to 3.5mm jack
            result = subprocess.run(['amixer', 'cset', 'numid=3', '1'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning(f"Failed to set audio output: {result.stderr}")
                return False
            
            # Set volume to 80%
            result = subprocess.run(['amixer', 'set', 'Master', '80%'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning(f"Failed to set volume: {result.stderr}")
                return False
            
            logger.info("Audio configured for 3.5mm jack at 80% volume")
            return True
            
        except subprocess.TimeoutExpired:
            logger.warning("Audio configuration timed out")
            return False
        except Exception as e:
            logger.error(f"Audio configuration error: {e}")
            return False

    @staticmethod
    def test_audio_output():
        """Test if audio is working"""
        try:
            # Quick silent test that doesn't produce sound
            result = subprocess.run(['amixer', 'get', 'Master'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and "80%" in result.stdout:
                logger.info("Audio configuration verified")
                return True
            return False
        except Exception as e:
            logger.warning(f"Audio test failed: {e}")
            return False

    @staticmethod
    def get_audio_status():
        """Get current audio configuration status"""
        try:
            result = subprocess.run(['amixer', 'cget', 'numid=3'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if "values=1" in result.stdout:
                    return "3.5mm jack"
                elif "values=2" in result.stdout:
                    return "HDMI"
                else:
                    return f"Unknown: {result.stdout}"
            return "Error getting status"
        except Exception as e:
            return f"Error: {e}"
