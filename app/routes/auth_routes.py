import jwt
from flask import Blueprint, jsonify, request
from app.models import *

from werkzeug.security import check_password_hash, generate_password_hash
from app import db
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
import cloudinary.uploader

auth = Blueprint("auth", __name__)

# api đăng nhập
@auth.route("/login", methods=["POST"])
def login():
    username = request.json.get("username", None)
    password = request.json.get("password", None)

    if not username or not password:
        return jsonify({"error": "Thiếu username hoặc password"}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Sai username hoặc password"}), 401

    access_token = create_access_token(identity=username)

    return jsonify({
        "message": "Đăng nhập thành công",
        "access_token": "Bearer " + access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "status": user.status
        }
    })

# api đăng ký
@auth.route("/register", methods=["POST"])
def register():
    try:
        data = request.form.to_dict()
        full_name = data.get("full_name")
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        avatar_file = request.files.get("avatar_url")

        if not username or not password or not email:
            return jsonify({"error": "Thiếu username hoặc password"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "username đã tồn tại"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "email đã tồn tại"}), 400

        avatar_url = None
        if avatar_file:
            upload_ = cloudinary.uploader.upload(avatar_file, folder="avatars")
            avatar_url = upload_.get("secure_url")

        # mã hóa mật khẩu
        hashed_pass = generate_password_hash(password)
        new_user = User(
            username=username,
            password=hashed_pass,
            full_name=full_name,
            email=email,
            avatar_url=avatar_url,
            created_at=datetime.utcnow()
        )

        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            "message": "Đăng ký thành công",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "full_name": new_user.full_name,
                "email": new_user.email,
                "avatar_url": new_user.avatar_url,
                "created_at": new_user.created_at
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
