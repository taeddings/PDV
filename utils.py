import re
import os
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_fixed
import requests
from config import logger

def is_valid_url(url):
    regex = re.compile(
        r'^(?:https?|ftp)://'  # http or https
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def detect_download_mode(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if "youtube.com" in domain or "youtu.be" in domain:
        return "youtube", "video" in url
    elif "archive.org" in domain:
        return "archive", False
    return None, None

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def download_youtube_content(url, audio_only):
    import yt_dlp
    ydl_opts = {
        "format": "bestaudio/best" if audio_only else "bestvideo+bestaudio/best",
        "outtmpl": os.path.join(config['download_dir'], "%(title)s.%(ext)s"),
        "quiet": True,
        "progress_hooks": [lambda d: update_progress(d)]
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return f"Downloaded: {info['title']}"
    except Exception as e:
        logger.error(f"Error downloading from YouTube: {e}")
        raise

import aiohttp
import asyncio

async def download_from_internet_archive(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                filename = os.path.join(config['download_dir'], os.path.basename(urlparse(url).path))
                with open(filename, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                return f"Downloaded: {filename}"
        except aiohttp.ClientError as e:
            logger.error(f"Error downloading from Internet Archive: {e}")
            return f"Error: {e}"

from threading import Lock
progress_lock = Lock()

def update_progress(d):
    with progress_lock:
        global current_progress, current_status
        if d['status'] == 'downloading':
            current_progress = float(d['_percent_str'].replace('%', ''))
            current_status = f"Downloading: {d['_percent_str']} at {d['_speed_str']}"
        elif d['status'] == 'finished':
            current_progress = 100
            current_status = "Download completed"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_ai_response(user_input):
    try:
        # URL for Ollama API, assuming it runs on localhost at port 11434
        url = "http://localhost:11434/api/generate"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-r1:1.5b",  # Change this to the model name you're using
            "prompt": user_input,
            "stream": False  # If you want a non-streaming response
        }
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        if 'response' in result:
            return result['response']
        else:
            logger.warning("Unexpected response format from AI: %s", result)
            return "AI encountered an issue with processing your request."
    except requests.RequestException as e:
        logger.error(f"Failed to get AI response: {e}")
        return "Sorry, the AI service is currently unavailable."
    except ValueError:  # JSON decode error
        logger.error("Failed to decode JSON response from AI")
        return "Error processing AI response."
