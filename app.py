from flask import Flask, request, render_template, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import threading
import time
import atexit
import asyncio
from config import config, logger
from ollama_manager import ollama_manager
from utils import (
    is_valid_url, detect_download_mode, download_youtube_content, 
    download_from_internet_archive, update_progress, get_ai_response
)
from models import db, migrate, Download, Conversation, User

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yourdatabase.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
migrate.init_app(app, db)

socketio = SocketIO(app)

current_progress = 0.0
current_status = ""

@app.route("/", methods=["GET"])
def index():
    return render_template('main.html', current_progress=current_progress, current_status=current_status)

@socketio.on('get_progress')
def send_progress():
    emit('progress_update', {'progress': current_progress, 'status': current_status})

@app.route("/progress")
def progress():
    return jsonify({'progress': current_progress, 'status': current_status})

@app.route("/download_youtube_video", methods=["POST"])
def download_youtube_video():
    youtube_url = request.form.get("youtube_url")
    download = Download(url=youtube_url, type='video')
    db.session.add(download)
    db.session.commit()
    
    message = download_youtube_content(youtube_url, audio_only=False)
    download.status = 'completed'
    download.progress = 100.0
    db.session.commit()
    return render_template('main.html', message=message, current_progress=current_progress, current_status=current_status)

@app.route("/download_youtube_audio", methods=["POST"])
def download_youtube_audio():
    youtube_url = request.form.get("youtube_audio_url")
    download = Download(url=youtube_url, type='audio')
    db.session.add(download)
    db.session.commit()
    
    message = download_youtube_content(youtube_url, audio_only=True)
    download.status = 'completed'
    download.progress = 100.0
    db.session.commit()
    return render_template('main.html', message=message, current_progress=current_progress, current_status=current_status)

@app.route("/download_archive", methods=["POST"])
def download_archive():
    archive_url = request.form.get("archive_url")
    download = Download(url=archive_url, type='archive')
    db.session.add(download)
    db.session.commit()
    
    message = asyncio.run(download_from_internet_archive(archive_url))
    download.status = 'completed'
    download.progress = 100.0
    db.session.commit()
    return render_template('main.html', message=message, current_progress=current_progress, current_status=current_status)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        if user_input:
            # Assuming user management, here we're just using a dummy user_id
            user_conversation = Conversation(user_id=1, message=user_input, role='User')
            db.session.add(user_conversation)
            db.session.commit()
            
            if is_valid_url(user_input):
                service, audio_only = detect_download_mode(user_input)
                if service == "archive":
                    msg = asyncio.run(download_from_internet_archive(user_input))
                    assistant_response = f"(Auto-Downloaded Archive) {msg}"
                elif service == "youtube":
                    msg = download_youtube_content(user_input, audio_only)
                    mode = "Audio" if audio_only else "Video"
                    assistant_response = f"(Auto-Downloaded YouTube {mode}) {msg}"
                else:
                    assistant_response = "Unrecognized link."
            else:
                # Use AI to generate a response
                assistant_response = get_ai_response(user_input)
            
            assistant_conversation = Conversation(user_id=1, message=assistant_response, role='Assistant')
            db.session.add(assistant_conversation)
            db.session.commit()
    
    conversations = Conversation.query.filter_by(user_id=1).order_by(Conversation.timestamp).all()
    return render_template('chat.html', conversation=[(conv.role, conv.message) for conv in conversations])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    
    try:
        if not ollama_manager.start_server():
            logger.error("Ollama server failed to start. Exiting.")
            exit(1)
        
        server_thread = threading.Thread(target=lambda: socketio.run(app, host="127.0.0.1", port=8080))
        server_thread.start()

        time.sleep(1)  # Delay to ensure the server is fully running
        import webbrowser
        webbrowser.open("http://127.0.0.1:8080", new=2)

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        ollama_manager.stop_server()