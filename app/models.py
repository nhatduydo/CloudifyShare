from app import db
from datetime import datetime
import enum

class BaseModel(db.Model):
    __abstract__ = True
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    update_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    
class User(BaseModel):
    __tablename__="users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(150), unique=True)
    avatar_url = db.Column(db.String(255))
    status = db.Column(db.Boolean, default=False) # False = offline, True = online
    
    # 1-n => user >< file
    files = db.relationship("File", back_populates="uploader", lazy=True)
    
    # Tin nhắn gửi và nhận
    sent_messages = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        lazy=True
    )
    received_messages = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        lazy=True
    )
    
    def __repr__(self):
        return f"<User {self.username}>"
    
class File(BaseModel):
    __tablename__ = "files"
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    upload_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_public = db.Column(db.Boolean, default=False)
    
    uploader = db.relationship("User", back_populates="files")
    
    message = db.relationship("Message", back_populates="attached_file", uselist=False)
    
    def __repr__(self):
        return f"<File {self.filename}>"

class MessageType(enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VIDEO = "video"
    AUDIO = "audio"

class Message(BaseModel):
    __tablename__ = "messages"
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text)
    message_type = db.Column(db.Enum(MessageType), default=MessageType.TEXT, nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("files.id"), nullable=True)
    
    sender= db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    
    attached_file = db.relationship("File", back_populates="message", uselist=False)
    
    def __repr__(self):
        return f"<Message {self.sender_id} => {self.receiver_id}>"
    
