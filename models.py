from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50))  # 'video', 'audio', or 'archive'
    status = db.Column(db.String(50), default='pending')  # 'pending', 'downloading', 'completed', 'error'
    progress = db.Column(db.Float, default=0.0)
    filename = db.Column(db.String(255))  # Name of the downloaded file
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Download {self.id} - {self.url}>'

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'User' or 'Assistant'
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship('User', back_populates='conversations')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    conversations = db.relationship('Conversation', back_populates='user')

    def __repr__(self):
        return f'<User {self.username}>'