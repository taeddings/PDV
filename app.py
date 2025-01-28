import os
import asyncio
import threading
import time
from uuid import uuid4
from flask import Flask, request, render_template, jsonify, url_for
from flask_socketio import SocketIO, emit
from config import config, logger
from ollama_manager import ollama_manager
from utils import (
    is_valid_url, detect_download_mode, download_youtube_content,
    download_from_internet_archive, get_ai_response
)
from models import db, migrate, Download, Conversation, User

# Initialize Flask app
app = Flask(__name__, static_url_path='/static', static_folder='static')

# Configure secret key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', str(uuid4()))

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yourdatabase.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
socketio = SocketIO(app)

# Global progress tracking (per user)
progress_data = {}

def set_progress(user_id, progress, status):
    progress_data[user_id] = {'progress': progress, 'status': status}

def get_progress(user_id):
    return progress_data.get(user_id, {'progress': 0.0, 'status': 'Not started'})

@app.route("/", methods=["GET"])
def index():
    user_id = request.args.get("user_id", 1)  # Replace with dynamic user authentication
    progress = get_progress(user_id)
    return render_template('main.html', current_progress=progress['progress'], current_status=progress['status'])

@socketio.on('get_progress')
def send_progress(data):
    user_id = data.get('user_id', 1)  # Replace with authenticated user ID
    progress = get_progress(user_id)
    emit('progress_update', {'progress': progress['progress'], 'status': progress['status']})

@app.route("/progress")
def progress():
    user_id = request.args.get("user_id", 1)  # Replace with authenticated user ID
    return jsonify(get_progress(user_id))

async def handle_download(download_func, url, user_id, audio_only=False):
    try:
        set_progress(user_id, 0.0, "Starting download...")
        message = await download_func(url, audio_only=audio_only)
        set_progress(user_id, 100.0, "Download complete")
        return message
    except Exception as e:
        logger.error(f"Download error for user {user_id}: {e}")
        set_progress(user_id, 0.0, "Download failed")
        return "An error occurred during the download."

@app.route("/download", methods=["POST"])
def download():
    user_id = request.form.get("user_id", 1)
    url = request.form.get("url")
    download_type = request.form.get("type", "video")  # 'video', 'audio', or 'archive'

    download = Download(url=url, type=download_type, user_id=user_id)
    db.session.add(download)
    db.session.commit()

    if download_type == "archive":
        message = asyncio.run(handle_download(download_from_internet_archive, url, user_id))
    else:
        audio_only = (download_type == "audio")
        message = asyncio.run(handle_download(download_youtube_content, url, user_id, audio_only))

    download.status = "completed" if "complete" in message else "failed"
    download.progress = 100.0 if "complete" in message else 0.0
    db.session.commit()

    progress = get_progress(user_id)
    return render_template('main.html', message=message, current_progress=progress['progress'], current_status=progress['status'])

@app.route("/chat", methods=["GET", "POST"])
def chat():
    user_id = request.args.get("user_id", 1)  # Replace with dynamic user authentication
    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        if user_input:
            user_conversation = Conversation(user_id=user_id, message=user_input, role="User")
            db.session.add(user_conversation)

            if is_valid_url(user_input):
                service, audio_only = detect_download_mode(user_input)
                if service == "archive":
                    msg = asyncio.run(download_from_internet_archive(user_input))
                    assistant_response = f"(Downloaded Archive) {msg}"
                elif service == "youtube":
                    msg = download_youtube_content(user_input, audio_only)
                    mode = "Audio" if audio_only else "Video"
                    assistant_response = f"(Downloaded YouTube {mode}) {msg}"
                else:
                    assistant_response = "Unrecognized link."
            else:
                assistant_response = get_ai_response(user_input)

            assistant_conversation = Conversation(user_id=user_id, message=assistant_response, role="Assistant")
            db.session.add(assistant_conversation)
            db.session.commit()

    conversations = Conversation.query.filter_by(user_id=user_id).order_by(Conversation.timestamp).all()
    return render_template("chat.html", conversation=[(conv.role, conv.message) for conv in conversations])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Ensure database tables exist

    try:
        if not ollama_manager.start_server():
            logger.error("Failed to start Ollama server. Exiting.")
            exit(1)

        server_thread = threading.Thread(target=lambda: socketio.run(app, host="127.0.0.1", port=8080))
        server_thread.start()

        import webbrowser
        webbrowser.open("http://127.0.0.1:8080", new=2)

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        ollama_manager.stop_server()
