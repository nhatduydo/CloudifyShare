from app import db
from app.models import *
from firebase_admin import db as firebase_db
from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from app import reader_engine
from dotenv import load_dotenv
from minio import Minio
import os
import io
import mimetypes
from urllib.parse import quote

messsage = Blueprint("message", __name__)

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET_NAME")
FRONTEND_BASE_URL = (os.getenv("FRONTEND_BASE_URL") or "").rstrip("/")

if not all([MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET]):
    raise RuntimeError("Missing MinIO configuration for message routes")

_internal_host = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
_internal_secure = MINIO_ENDPOINT.startswith("https")

minio_client = Minio(
    _internal_host,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=_internal_secure
)

if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)


def _build_download_url(file_id: int, mode: str) -> str:
    base = FRONTEND_BASE_URL or ""
    prefix = base or ""
    return f"{prefix}/files/download/{file_id}?mode={mode}"

# api gửi tin nhắn


@messsage.route("/send", methods=["POST"])
@jwt_required()
def send_message():
    try:
        data = request.form.to_dict()
        sender_username = get_jwt_identity()
        receiver_id = data.get("receiver_id")
        content = data.get("content", "")
        message_type_raw = data.get("message_type", "text").lower()
        file = request.files.get("file")

        try:
            message_type_enum = MessageType(message_type_raw)
        except ValueError:
            message_type_enum = MessageType.TEXT

        sender = User.query.execution_options(bind=reader_engine).filter_by(username=sender_username).first()
        if not sender:
            return jsonify({"error": "Người gửi không hợp lệ"}), 400
        if not receiver_id:
            return jsonify({"error": "Thiếu receiver_id"}), 400
        try:
            receiver_id = int(receiver_id)
        except (TypeError, ValueError):
            return jsonify({"error": "receiver_id không hợp lệ"}), 400

        file_obj = None
        if file:
            file_bytes = file.read()
            file_size = len(file_bytes)
            file_stream = io.BytesIO(file_bytes)

            content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

            try:
                minio_client.put_object(
                    MINIO_BUCKET,
                    file.filename,
                    file_stream,
                    length=file_size,
                    content_type=content_type
                )
            except Exception as upload_err:
                return jsonify({"error": f"Không thể lưu file lên MinIO: {upload_err}"}), 500

            file_obj = File(
                filename=file.filename,
                file_url="",
                file_size=file_size,
                file_type=content_type,
                upload_by=sender.id,
                is_public=True
            )
            db.session.add(file_obj)
            db.session.flush()

            mode = "inline" if message_type_enum == MessageType.IMAGE else "attachment"
            file_obj.file_url = _build_download_url(file_obj.id, mode)
            db.session.commit()
        new_msg = Message(
            sender_id=sender.id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type_enum,
            file_id=file_obj.id if file_obj else None,
            created_at=datetime.utcnow()
        )
        db.session.add(new_msg)
        db.session.commit()

        chat_id = f"{min(sender.id, int(receiver_id))}_{max(sender.id, int(receiver_id))}"
        ref = firebase_db.reference(f"messages/{chat_id}")
        ref.push({
            "id": new_msg.id,
            "sender_id": new_msg.sender_id,
            "receiver_id": new_msg.receiver_id,
            "content": new_msg.content,
            "message_type": new_msg.message_type.value,
            "file_id": file_obj.id if file_obj else None,
            "file_url": file_obj.file_url if file_obj else None,
            "timestamp": new_msg.created_at.isoformat()
        })

        sender_info = {
            "id": sender.id,
            "username": sender.username,
            "full_name": sender.full_name,
            "avatar_url": sender.avatar_url,
            "email": sender.email,
        }

        receiver = User.query.execution_options(bind=reader_engine).get(receiver_id)
        receiver_info = {
            "id": receiver.id,
            "username": receiver.username,
            "full_name": receiver.full_name,
            "avatar_url": receiver.avatar_url,
            "email": receiver.email,
        }

        return jsonify({
            "message": "Gửi tin nhắn thành công",
            "data": {
                "id": new_msg.id,
                "content": new_msg.content,
                "message_type": new_msg.message_type.value,
                "file_id": file_obj.id if file_obj else None,
                "file_name": file_obj.filename if file_obj else None,
                "file_type": file_obj.file_type if file_obj else None,
                "file_url": file_obj.file_url if file_obj else None,
                "created_at": new_msg.created_at,
                "sender": sender_info,
                "receiver": receiver_info
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# api lấy lịch sử chat
@messsage.route("/conversation/<int:receiver_id>", methods=["GET"])
@jwt_required()
def get_conversation(receiver_id):
    try:
        current_username = get_jwt_identity()
        current_user = User.query.execution_options(bind=reader_engine).filter_by(username=current_username).first()

        if not current_user:
            return jsonify({"error": "Người dùng không hợp lệ"}), 400

        messages = Message.query.execution_options(bind=reader_engine).filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id)) |
            ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.asc()).all()

        result = []
        for mess in messages:
            file_payload = None
            if mess.attached_file:
                mode = "inline" if mess.message_type == MessageType.IMAGE else "attachment"
                file_payload = {
                    "file_id": mess.attached_file.id,
                    "file_name": mess.attached_file.filename,
                    "file_type": mess.attached_file.file_type,
                    "file_url": _build_download_url(mess.attached_file.id, mode)
                }

            result.append({
                "id": mess.id,
                "sender_id": mess.sender_id,
                "receiver_id": mess.receiver_id,
                "content": mess.content,
                "message_type": mess.message_type.value,
                "file_id": file_payload["file_id"] if file_payload else None,
                "file_name": file_payload["file_name"] if file_payload else None,
                "file_type": file_payload["file_type"] if file_payload else None,
                "file_url": file_payload["file_url"] if file_payload else None,
                "created_at": mess.created_at
            })
        return jsonify({"messages": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# api danh sách người đã từng nhắn tin


@messsage.route("/list", methods=["GET"])
@jwt_required()
def get_chat_list():
    try:
        current_username = get_jwt_identity()
        current_user = User.query.execution_options(bind=reader_engine).filter_by(username=current_username).first()

        if not current_user:
            return jsonify({"error": "Không tìm thấy người dùng"}), 400

        sent_messages = Message.query.filter_by(sender_id=current_user.id).all()
        received_messages = Message.query.filter_by(receiver_id=current_user.id).all()

        chat_partner_ids = []

        for msg in sent_messages:
            chat_partner_ids.append(msg.receiver_id)

        for msg in received_messages:
            chat_partner_ids.append(msg.sender_id)

        chat_partner_ids = list(set(chat_partner_ids))

        chat_partners = User.query.filter(User.id.in_(chat_partner_ids)).all()

        result = []
        for user in chat_partners:
            result.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "status": user.status
            })

        return jsonify({"chats": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# api tìm kiếm user theo username hoặc full_name hoặc id
@messsage.route("/search", methods=["GET"])
@jwt_required()
def search_user():
    try:
        current_username = get_jwt_identity()
        keyword = request.args.get("q", "").strip()

        if not keyword:
            return jsonify({"error": "Thiếu keyword"}), 400

        query = User.query.execution_options(bind=reader_engine).filter(User.username != current_username)

        if keyword.isdigit():
            query = query.filter(User.id == int(keyword))

        else:
            query = query.filter(
                (User.username.ilike(f"%{keyword}%")) |
                (User.full_name.ilike(f"%{keyword}%"))
            )
        users = query.all()

        results = []
        for user in users:
            user_data = {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "status": user.status
            }
            results.append(user_data)

        return jsonify({
            "count": len(results),
            "users": results
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 404
