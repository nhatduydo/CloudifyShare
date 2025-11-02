from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
from flask_migrate import Migrate
from flask_cors import CORS
import cloudinary
import firebase_admin
from firebase_admin import credentials, db as firebase_db 
from flask_jwt_extended import JWTManager

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object("app.config.Config")
    
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        print("JWT unauthorized: Missing or invalid token")
        return jsonify({"error": "Unauthorized"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        print("JWT invalid token:", reason)
        return jsonify({"error": "Invalid token"}), 422

    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    
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
    
    from app.routes.auth_routes import auth
    from app.routes.message_routes import messsage
    from app.routes.file_routes import file
    from app.routes.main_routes import main
    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(messsage, url_prefix="/messages")
    app.register_blueprint(file, url_prefix="/files")
    app.register_blueprint(main, url_prefix="/")
    
    from app import models
    return app