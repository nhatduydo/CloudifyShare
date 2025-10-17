from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
from flask_migrate import Migrate
from flask_cors import CORS
import cloudinary
import firebase_admin
from firebase_admin import credentials, db

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object("app.config.Config")
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    cloudinary.config(
        cloud_name = app.config["CLOUDINARY_CLOUD_NAME"],
        api_key = app.config["CLOUDINARY_API_KEY"],
        api_secret = app.config["CLOUDINARY_API_SECRET"],
        secure=True
    )
    print("Cloudinary connected!")
    
    try:
        cred_path = app.config["FIREBASE_CREDENTIAL_PATH"]
        db_url = app.config["FIREBASE_DATABASE_URL"]
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {"databaseURL": db_url})
            print("Firebase Realtime Database connected!")
        else:
            print("Firebase already initialized.")
    except Exception as e:
        print("Firebase init error:", e)
    
    
    from app import models
    return app