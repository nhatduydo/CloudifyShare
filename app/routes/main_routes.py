from flask import Blueprint, render_template, request
from flask_jwt_extended import decode_token

main = Blueprint("main", __name__)

@main.context_processor
def inject_user():
    token = request.cookies.get('access_token')
    user = None
    if token:
        try:
            data = decode_token(token)
            user = {
                "name": data.get("name"),
                "email": data.get("email"),
                "avatar_url": data.get("avatar_url")
            }
        except Exception:
            pass
    return dict(user=user)

@main.route("/")
def home():
    token = request.cookies.get('access_token')
    user = None

    if token:
        try:
            data = decode_token(token)
            user = {
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url")
            }
        except Exception:
            pass

    return render_template("home.html", user=user)

@main.route("/login")
def login_page():
    return render_template("login.html")

@main.route("/register")
def register_page():
    return render_template("register.html")

@main.route("/dashboard")
def dashboard_page():
    token = request.cookies.get('access_token')
    user = None

    if token:
        try:
            data = decode_token(token)
            user = {
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url")
            }
        except Exception:
            pass

    return render_template("dashboard.html", user=user)

@main.route("/dashboard/messages")
def messages_page():
    token = request.cookies.get('access_token')
    user = None

    if token:
        try:
            data = decode_token(token)
            user = {
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url")
            }
        except Exception:
            pass
    return render_template("partials/messages.html", user=user)

@main.route("/dashboard/storage")
def storage_page():
    token = request.cookies.get('access_token')
    user = None

    if token:
        try:
            data = decode_token(token)
            user = {
                "name": data.get("name"),
                "email": data.get("email"),
                "avatar_url": data.get("avatar_url")
            }
        except Exception:
            pass

    return render_template("partials/storage.html", user=user)


@main.route("/dashboard/profile")
def profile_page():
    token = request.cookies.get('access_token')
    user = None

    if token:
        try:
            data = decode_token(token)
            user = {
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url")
            }
        except Exception:
            pass
    return render_template("partials/profile.html", user=user)

@main.route("/dashboard/settings")
def settings_page():
    token = request.cookies.get('access_token')
    user = None

    if token:
        try:
            data = decode_token(token)
            user = {
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url")
            }
        except Exception:
            pass
    return render_template("partials/settings.html", user=user)

@main.route("/admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")