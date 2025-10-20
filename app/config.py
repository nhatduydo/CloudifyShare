import os
from datetime import timedelta

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://admin:Admin%23123@cloudsharedb.cclau0qkccdx.us-east-1.rds.amazonaws.com:3306/cloudsharedb"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Cloudinary
    CLOUDINARY_CLOUD_NAME= os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY= os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET= os.getenv("CLOUDINARY_API_SECRET")

    # Firebase
    FIREBASE_CREDENTIAL_PATH = os.getenv("FIREBASE_CREDENTIAL_PATH", "app/firebase.json")
    FIREBASE_DATABASE_URL = os.getenv(
        "FIREBASE_DATABASE_URL",
        "https://cloudifyshare-default-rtdb.asia-southeast1.firebasedatabase.app/"
    )
    
    # JWT 
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 36000)))