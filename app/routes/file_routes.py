from flask import Blueprint, request, jsonify
import boto3, os
from botocore.exceptions import NoCredentialsError
from dotenv import load_dotenv
from app.models import *
from flask_jwt_extended import jwt_required, get_jwt_identity
from urllib.parse import quote
load_dotenv()

file = Blueprint("file", __name__)

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

# kết nối s3 client
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# api upload file
@file.route("/upload", methods=['POST'])
@jwt_required()
def upload_file():
    try:
        current_username = get_jwt_identity()
        current_user = User.query.filter_by(username=current_username).first()
        if not current_user:
            return jsonify({"error": "Không tìm thấy user"}), 404
        
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "Thiếu file upload"}), 400
        
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            file.filename,
            ExtraArgs={"ContentType": file.content_type}
        )
        
        encoded_key = quote(file.filename, safe="")
        file_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{encoded_key}"
        
        new_file = File(
            filename=file.filename,
            file_url=file_url,
            file_size=request.content_length or 0,
            file_type=file.content_type,
            upload_by=current_user.id,
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
    
    except NoCredentialsError:
        return jsonify({"error", }), 400     
    
# API lấy danh sách file
@file.route("/list", methods=["GET"])
@jwt_required()
def list_files():
    current_username = get_jwt_identity()
    current_user = User.query.filter_by(username=current_username).first()
    
    if not current_user:
        return jsonify({"error": "Không tìm thấy user"}), 404
    
    user_file_records = File.query.filter_by(upload_by=current_user.id).order_by(File.created_at.desc()).all()
    
    file_list = []
    for file_record in user_file_records:
        file_list.append({
             "id": file_record.id,
            "filename": file_record.filename,
            "url": file_record.file_url,
            "type": file_record.file_type,
            "size": file_record.file_size,
            "created_at": file_record.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return jsonify(file_list), 200

# api xóa file 
@file.route("/delete/<int:file_id>", methods=["DELETE"])
@jwt_required()
def delete_file(file_id):
    try:
        current_username = get_jwt_identity()
        current_user = User.query.filter_by(username=current_username).first()
        
        if not current_user:
            return jsonify({"error": "Không tìm thấy user"}), 404
        
        file = File.query.filter_by(id=file_id, upload_by=current_user.id).first()
        if not file:
            return jsonify({"error": "Không tìm thấy file hoặc bạn không có quyền xóa"}), 404
        
        # xóa trên S3
        s3.delete_object(Bucket=S3_BUCKET, Key=file.filename)
        
        # Xóa trong DB
        db.session.delete(file)
        db.session.commit()
        
        return jsonify({"message": f"Đã xóa file '{file.filename}' thành công"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@file.route("/download/<int:file_id>", methods=["GET"])
@jwt_required()
def download_file(file_id):
    try:
        current_username = get_jwt_identity()
        current_user = User.query.filter_by(username=current_username).first()
        
        if not current_user:
            return jsonify({"error": "Không tìm thấy user"}), 404
        
        file_record = File.query.filter_by(id=file_id, upload_by=current_user.id).first()
        if not file_record:
            return jsonify({"error": "Không tìm thấy file hoặc bạn không có quyền tải"}), 404

        download_link = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": file_record.filename,
                "ResponseContentDisposition": f"attachment; filename={file_record.filename}"
            },
            ExpiresIn=60 * 60 * 24 * 7
        )
        
        return jsonify({
            "message": "Tạo link tải thành công (hết hạn sau 7 ngày)",
            "download_link": download_link
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# api chia sẻ - bật public
@file.route("/make_public/<int:file_id>", methods=["PUT"])
@jwt_required()
def make_file_public(file_id):
    try:
        current_username = get_jwt_identity()
        current_user = User.query.filter_by(username = current_username).first()
        
        if not current_user:
            return jsonify({"error": "Không tìm thấy user"}), 404
        
        file_record = File.query.filter_by(id=file_id, upload_by=current_user.id).first()
        if not file_record:
            return jsonify({"error": "Không tìm thấy file"}), 404
        
        # cập nhập s3 ACL (access control list)
        s3.put_object_acl(ACL="public-read", Bucket=S3_BUCKET, Key=file_record.filename)
        
        file_record.is_public = True
        db.session.commit()
        
        encoded_key = quote(file_record.filename, safe="")
        
        public_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{encoded_key}"
        
        return jsonify({
            "message": "File đã được chia sẻ công khai vĩnh viễn!",
            "public_url": public_url
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 404

# api tắt chia sẻ
@file.route("/make_private/<int:file_id>", methods=["PUT"])
@jwt_required()
def make_file_private(file_id):
    try:
        current_username = get_jwt_identity()
        current_user = User.query.filter_by(username=current_username).first()
        
        if not current_user:
            return jsonify({"error", "Không tìm thấy user"}), 404
        
        file_record = File.query.filter_by(id=file_id, upload_by=current_user.id).first()
        
        if not file_record:
            return jsonify({"error": "Không tìm thấy file"}), 404
        
        s3.put_object_acl(ACL="private", Bucket=S3_BUCKET, Key=file_record.filename)
        file_record.is_public = False
        db.session.commit()

        return jsonify({"message": "File đã được chuyển sang chế độ private"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 404
    
    