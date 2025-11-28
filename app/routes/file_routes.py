from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, User, File
from dotenv import load_dotenv
from minio import Minio
from urllib.parse import quote
import os
import io
from datetime import timedelta
import json
from flask import send_file
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app import reader_engine

load_dotenv()
file = Blueprint("file", __name__)

# Kết nối MinIO client
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET_NAME")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL")
DOWNLOAD_TOKEN_SALT = os.getenv("DOWNLOAD_TOKEN_SALT", "download-file-token")
DOWNLOAD_TOKEN_MAX_AGE = int(os.getenv("DOWNLOAD_TOKEN_MAX_AGE", 60 * 60 * 24 * 7))

# Client nội bộ – dùng IP private
_internal_host = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
_internal_secure = MINIO_ENDPOINT.startswith("https")

minio_client = Minio(
    _internal_host,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=_internal_secure
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
        user = User.query.execution_options(bind=reader_engine).filter_by(username=current_user).first()

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

        # Tạo bản ghi không có URL trước
        new_file = File(
            filename=file_obj.filename,
            file_url="",
            file_size=request.content_length or 0,
            file_type=file_obj.content_type,
            upload_by=user.id,
            is_public=False
        )
        db.session.add(new_file)  # write → master
        db.session.commit()

        # Cập nhật URL download
        new_file.file_url = f"{FRONTEND_BASE_URL}/files/download/{new_file.id}"
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
    user = User.query.execution_options(bind=reader_engine).filter_by(username=current_user).first()
    if not user:
        return jsonify({"error": "Không tìm thấy user"}), 404

    files = File.query.execution_options(bind=reader_engine)\
        .filter_by(upload_by=user.id)\
        .order_by(File.created_at.desc()).all()
    file_list = [{
        "id": f.id,
        "filename": f.filename,
        "url": f.file_url,
        "type": f.file_type,
        "size": f.file_size,
        "is_public": f.is_public,
        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M:%S")
    } for f in files]

    return jsonify(file_list), 200


# Xóa file
@file.route("/delete/<int:file_id>", methods=["DELETE"])
@jwt_required()
def delete_file(file_id):
    try:
        current_user = get_jwt_identity()
        user = User.query.execution_options(bind=reader_engine).filter_by(username=current_user).first()
        file = File.query.execution_options(bind=reader_engine).filter_by(id=file_id, upload_by=user.id).first()

        if not file:
            return jsonify({"error": "Không tìm thấy file"}), 404

        minio_client.remove_object(MINIO_BUCKET, file.filename)
        db.session.delete(file)
        db.session.commit()
        return jsonify({"message": f"Đã xóa file '{file.filename}' thành công"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@file.route("/download/<int:file_id>", methods=["GET"])
def download_file(file_id):
    file_record = File.query.filter_by(id=file_id).first()
    if not file_record:
        return jsonify({"error": "Không tìm thấy file"}), 404

    # Link công khai chỉ hoạt động khi file đang ở trạng thái public
    if not file_record.is_public:
        return jsonify({"error": "File đã được đặt ở chế độ riêng tư"}), 403
    
    try:
        response = minio_client.get_object(MINIO_BUCKET, file_record.filename)

        # ép download hoặc xem inline
        mode_param = request.args.get("mode", "attachment")
        disposition_mode = "inline" if mode_param == "inline" else "attachment"

        return Response(
            response,
            mimetype=file_record.file_type,
            headers={
                "Content-Disposition": f"{disposition_mode}; filename={quote(file_record.filename)}",
                "Content-Length": response.getheader("Content-Length"),
                "Cache-Control": "no-cache, no-store",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Chia sẻ file (public)
@file.route("/make_public/<int:file_id>", methods=["PUT"])
@jwt_required()
def make_file_public(file_id):
    """
    Chia sẻ file công khai - tạo link để ai cũng có thể truy cập online
    Link sẽ dùng mode=inline để xem file trực tiếp trong browser
    """
    try:
        current_username = get_jwt_identity()
        current_user = User.query.execution_options(bind=reader_engine).filter_by(username=current_username).first()

        if not current_user:
            return jsonify({"error": "Không tìm thấy user"}), 404

        file_record = File.query.execution_options(bind=reader_engine).filter_by(id=file_id, upload_by=current_user.id).first()
        if not file_record:
            return jsonify({"error": "Không tìm thấy file"}), 404

        # Cập nhật trạng thái public trong database
        file_record.is_public = True
        db.session.commit()

        # Tạo link công khai với mode=inline để ai cũng có thể xem file trực tiếp online
        public_url = f"{FRONTEND_BASE_URL}/files/download/{file_id}?mode=inline"

        return jsonify({
            "message": "File đã được chia sẻ công khai vĩnh viễn!",
            "public_url": public_url
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# Tắt chia sẻ (private)
@file.route("/make_private/<int:file_id>", methods=["PUT"])
@jwt_required()
def make_file_private(file_id):
    try:
        current_username = get_jwt_identity()

        user = User.query.execution_options(bind=reader_engine).filter_by(username=current_username).first()
        file = File.query.execution_options(bind=reader_engine).filter_by(id=file_id, upload_by=user.id).first()

        if not file:
            return jsonify({"error": "Không tìm thấy file"}), 404

        # Revoke public access (bằng policy deny)
        minio_client.set_bucket_policy(MINIO_BUCKET, '{"Version":"2012-10-17","Statement":[]}')

        file.is_public = False
        db.session.commit()
        return jsonify({"message": "Đã tắt chia sẻ công khai"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
