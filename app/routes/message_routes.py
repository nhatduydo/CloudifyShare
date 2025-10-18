from app import db
from app.models import *
import cloudinary.uploader
from firebase_admin import db as firebase_db
from flask import Blueprint, jsonify, request

messsage = Blueprint("message", __name__)

@messsage.route("/send", methods=["POST"])
def send_message():
    pass