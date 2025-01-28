import subprocess
import signal
import psutil
from config import config, logger
import logging

class OllamaManager:
    def __init__(self, ollama_path):
        self.ollama_path = ollama_path
        self.process = None

    def start_server(self):
        try:
            self.process = subprocess.Popen(
                [self.ollama_path, "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            logger.info("Ollama server started.")
            return True
        except FileNotFoundError:
            logger.error(f"Ollama executable not found at {self.ollama_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to start Ollama server: {e}")
            return False

    def stop_server(self):
        if self.process:
            try:
                parent = psutil.Process(self.process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                logger.info("Ollama server stopped.")
            except Exception as e:
                logger.error(f"Failed to stop Ollama server: {e}")

ollama_manager = OllamaManager(config['ollama_path'])