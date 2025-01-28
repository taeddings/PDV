import os
import yaml
from logging.handlers import RotatingFileHandler

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f:
            f.write(yaml.dump({
                'download_dir': 'downloads',
                'log_file': 'logs/download_log.log',
                'ollama_path': 'ollama/ollama',
                'max_download_size': 100 * 1024 * 1024  # 100 MB
            }, default_flow_style=False))
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
handler = RotatingFileHandler(config['log_file'], maxBytes=1000000, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)