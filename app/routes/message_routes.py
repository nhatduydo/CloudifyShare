from app import db
from app.models import *
import cloudinary.uploader
from firebase_admin import db as firebase_db
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

messsage = Blueprint("message", __name__)

# api gửi tin nhắn
@messsage.route("/send", methods=["POST"])
@jwt_required()
def send_message():
    try:
        data = request.form.to_dict()
        sender_username = get_jwt_identity()
        receiver_id = data.get("receiver_id")
        content = data.get("content", "")
        message_type = data.get("message_type", "text").lower()
        file = request.files.get("file")
        
        sender = User.query.filter_by(username=sender_username).first()
        if not sender:
            return jsonify({"error": "Người gửi không hợp lệ"}), 400
        if not receiver_id:
            return jsonify({"error": "Thiếu receiver_id"}), 400
        
        # upload file nếu có
        file_obj = None
        if file:
            upload_ = cloudinary.uploader.upload(file, folder="message")
            file_obj = File(
                filename=upload_["original_filename"],
                file_url=upload_["secure_url"],
                file_type=message_type,
                upload_by=sender.id
            )
            db.session.add(file_obj)
            db.session.flush()
            
            # Lưu tin nhắn SQL
            new_msg = Message(
                sender_id=sender.id,
                receiver_id=receiver_id,
                content=content,
                message_type=MessageType(message_type),
                file_id=file_obj.id if file_obj else None,
                created_at=datetime.utcnow()
            )
            db.session.add(new_msg)
            db.session.commit()
            
            # Push lên Firebase
            chat_id = f"{min(sender.id, int(receiver_id))}_{max(sender.id, int(receiver_id))}"
            ref = firebase_db.reference(f"messages/{chat_id}")
            ref.push({
                "id": new_msg.id,
                "sender_id": new_msg.sender_id,
                "receiver_id": new_msg.receiver_id,
                "content": new_msg.content,
                "message_type": new_msg.message_type.value,
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

            receiver = User.query.get(receiver_id)
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
        current_user = User.query.filter_by(username=current_username).first()
        
        if not current_user:
            return jsonify({"error", "Người dùng không hợp lệ"}), 400
        
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id) | 
             (Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.asc()).all()
        
        result = []
        for mess in messages:
            result.append({
                "id": mess.id,
                "sender_id": mess.sender_id,
                "receiver_id": mess.receiver_id,
                "content": mess.content,
                "message_type": mess.message_type.value,
                "file_url": mess.attached_file.file_url if mess.attached_file else None,
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
        current_user = User.query.filter_by(username=current_username).first()

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
        
        query = User.query.filter(User.username != current_username)
        
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
