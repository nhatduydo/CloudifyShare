from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, User, File
from dotenv import load_dotenv
from minio import Minio
from urllib.parse import quote
import os, io
from datetime import timedelta
import json

load_dotenv()
file = Blueprint("file", __name__)

# Kết nối MinIO client
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET_NAME")
MINIO_ENDPOINT_PUBLIC = os.getenv("MINIO_ENDPOINT_PUBLIC")

minio_client = Minio(
    MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_ENDPOINT.startswith("https")
)

# Tạo bucket nếu chưa có
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)

# Upload file
@file.route("/upload", methods=["POST"])
@jwt_required()
def upload_file():
    try:
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        if not user:
            return jsonify({"error": "Không tìm thấy user"}), 404

        file_obj = request.files.get("file")
        if not file_obj:
            return jsonify({"error": "Thiếu file upload"}), 400

        # Upload file lên MinIO
        file_obj.seek(0)
        minio_client.put_object(
            MINIO_BUCKET,
            file_obj.filename,
            io.BytesIO(file_obj.read()),
            length=-1,
            part_size=10 * 1024 * 1024,
            content_type=file_obj.content_type
        )

        # nếu không đúng thì đổi qua cái này
        # file_url = f"{MINIO_ENDPOINT_PUBLIC}/{MINIO_BUCKET}/{quote(file_obj.filename)}"
        
        file_url = f"{MINIO_ENDPOINT_PUBLIC}/{quote(file_obj.filename)}"

        new_file = File(
            filename=file_obj.filename,
            file_url=file_url,
            file_size=request.content_length or 0,
            file_type=file_obj.content_type,
            upload_by=user.id,
            is_public=False
        )
        db.session.add(new_file)
        db.session.commit()

        return jsonify({
            "message": "Upload thành công!",
            "file": {
                "id": new_file.id,
                "name": new_file.filename,
                "url": new_file.file_url,
                "type": new_file.file_type,
                "size": new_file.file_size
            }
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Danh sách file của user
@file.route("/list", methods=["GET"])
@jwt_required()
def list_files():
    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()
    if not user:
        return jsonify({"error": "Không tìm thấy user"}), 404

    files = File.query.filter_by(upload_by=user.id).order_by(File.created_at.desc()).all()
    file_list = [{
        "id": f.id,
        "filename": f.filename,
        "url": f.file_url,
        "type": f.file_type,
        "size": f.file_size,
        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M:%S")
    } for f in files]

    return jsonify(file_list), 200


# Xóa file
@file.route("/delete/<int:file_id>", methods=["DELETE"])
@jwt_required()
def delete_file(file_id):
    try:
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        file = File.query.filter_by(id=file_id, upload_by=user.id).first()

        if not file:
            return jsonify({"error": "Không tìm thấy file"}), 404

        minio_client.remove_object(MINIO_BUCKET, file.filename)
        db.session.delete(file)
        db.session.commit()
        return jsonify({"message": f"Đã xóa file '{file.filename}' thành công"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# Download file (link tạm thời)
@file.route("/download/<int:file_id>", methods=["GET"])
@jwt_required()
def download_file(file_id):
    try:
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        file = File.query.filter_by(id=file_id, upload_by=user.id).first()
        if not file:
            return jsonify({"error": "Không tìm thấy file"}), 404

        presigned_url = minio_client.presigned_get_object(
            MINIO_BUCKET,
            file.filename,
            expires=timedelta(days=7),
            response_headers={
                "response-content-disposition": f'attachment; filename="{file.filename}"'
            }
        )
        internal_host = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
        public_host = MINIO_ENDPOINT_PUBLIC.replace("http://", "").replace("https://", "")

        public_signed = presigned_url.replace(f"http://{internal_host}", f"http://{public_host}")
        public_signed = public_signed.replace(f"https://{internal_host}", f"https://{public_host}")

        return jsonify({
            "message": "Tạo link tải thành công (hết hạn sau 7 ngày)",
            "download_link": public_signed 
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Chia sẻ file (public)
@file.route("/make_public/<int:file_id>", methods=["PUT"])
@jwt_required()
def make_file_public(file_id):
    try:
        user = User.query.filter_by(username=get_jwt_identity()).first()
        file = File.query.filter_by(id=file_id, upload_by=user.id).first()
        if not file:
            return jsonify({"error": "Không tìm thấy file"}), 404

        # public ACL có thể bật bằng policy
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{MINIO_BUCKET}/{file.filename}"]
            }]
        }
        minio_client.set_bucket_policy(MINIO_BUCKET, json.dumps(policy))
        file.is_public = True
        db.session.commit()

        return jsonify({
            "message": "File đã được chia sẻ công khai!",
            "public_url": file.file_url
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Tắt chia sẻ (private)
@file.route("/make_private/<int:file_id>", methods=["PUT"])
@jwt_required()
def make_file_private(file_id):
    try:
        user = User.query.filter_by(username=get_jwt_identity()).first()
        file = File.query.filter_by(id=file_id, upload_by=user.id).first()
        if not file:
            return jsonify({"error": "Không tìm thấy file"}), 404

        # Revoke public access (bằng policy deny)
        minio_client.set_bucket_policy(MINIO_BUCKET, '{"Version":"2012-10-17","Statement":[]}')

        file.is_public = False
        db.session.commit()
        return jsonify({"message": "Đã tắt chia sẻ công khai"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
