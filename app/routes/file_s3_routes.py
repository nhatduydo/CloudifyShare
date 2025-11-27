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
        db.session.add(new_file) # write → master
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
@jwt_required(optional=True)
def download_file(file_id):
    try:
        file_record = File.query.filter_by(id=file_id).first()
        
        if not file_record:
            return jsonify({"error": "Không tìm thấy file hoặc bạn không có quyền tải"}), 404

        serializer = URLSafeTimedSerializer(
            current_app.config["SECRET_KEY"],
            salt=DOWNLOAD_TOKEN_SALT
        )

        # Lấy JWT identity một lần
        current_username = get_jwt_identity()

        # Kiểm tra quyền truy cập
        if not file_record.is_public:
            authorized = False

            if current_username:
                current_user = User.query.filter_by(username=current_username).first()
                
                if not current_user:
                    return jsonify({"error": "Không tìm thấy user"}), 404

                if file_record.upload_by != current_user.id:
                    return jsonify({"error": "Không tìm thấy file hoặc bạn không có quyền tải"}), 404

                authorized = True
            else:
                # Cho phép truy cập nếu có token hợp lệ trong query
                token_param = request.args.get("token")
                if not token_param:
                    return jsonify({"error": "Unauthorized"}), 401

                try:
                    token_data = serializer.loads(token_param, max_age=DOWNLOAD_TOKEN_MAX_AGE)
                except SignatureExpired:
                    return jsonify({"error": "Link đã hết hạn"}), 401
                except BadSignature:
                    return jsonify({"error": "Token không hợp lệ"}), 401

                if token_data.get("file_id") != file_id:
                    return jsonify({"error": "Token không hợp lệ"}), 401

        
                authorized = True

            if not authorized:
                return jsonify({"error": "Unauthorized"}), 401

        # Kiểm tra nếu request từ frontend (có JWT token) thì trả về JSON link
        # Nếu không có JWT (truy cập trực tiếp từ browser) thì stream file trực tiếp
        wants_json = current_username is not None

        if wants_json:
            # Trả về JSON link cho frontend
            if file_record.is_public:
                download_link = f"{FRONTEND_BASE_URL}/files/download/{file_id}?mode=attachment"
            else:
                token_payload = {"file_id": file_id}
                token = serializer.dumps(token_payload)
                download_link = f"{FRONTEND_BASE_URL}/files/download/{file_id}?token={token}&mode=attachment"

            return jsonify({
                "message": "Tạo link tải thành công (hết hạn sau 7 ngày)",
                "download_link": download_link
            }), 200
        else:
            # Stream file trực tiếp cho browser (khi truy cập public link)
            try:
                file_obj = minio_client.get_object(MINIO_BUCKET, file_record.filename)
                file_data = file_obj.read()
                file_obj.close()
                file_obj.release_conn()
            except Exception as e:
                return jsonify({"error": f"Không thể lấy file từ MinIO: {str(e)}"}), 500

            disposition_mode = "inline" if request.args.get("mode") == "inline" else "attachment"

            # Tạo response với file data
            return Response(
                file_data,
                mimetype=file_record.file_type or 'application/octet-stream',
                headers={
                    "Content-Disposition": f"{disposition_mode}; filename={quote(file_record.filename)}"
                }
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Chia sẻ file (public)
@file.route("/make_public/<int:file_id>", methods=["PUT"])
@jwt_required()
def make_file_public(file_id):
    try:
        current_username = get_jwt_identity()
        current_user = User.query.execution_options(bind=reader_engine).filter_by(username=current_username).first()

        if not current_user:
            return jsonify({"error": "Không tìm thấy user"}), 404

        file_record = File.query.execution_options(bind=reader_engine).filter_by(id=file_id, upload_by=current_user.id).first()
        if not file_record:
            return jsonify({"error": "Không tìm thấy file"}), 404

        # Cập nhật trạng thái public trong database (MinIO private không cần set ACL)
        file_record.is_public = True
        db.session.commit()

        # Dùng FRONTEND_BASE_URL vì MinIO private không thể truy cập trực tiếp
        public_url = f"{FRONTEND_BASE_URL}/files/download/{file_id}?mode=inline"

        return jsonify({
            "message": "File đã được chia sẻ công khai vĩnh viễn!",
            "public_url": public_url
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 404


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
