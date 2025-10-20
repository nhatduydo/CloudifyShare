from flask import Blueprint, render_template

main = Blueprint("main", __name__)

@main.route("/")
def home():
    return render_template("home.html")

@main.route("/login")
def login_page():
    return render_template("login.html")

@main.route("/register")
def register_page():
    return render_template("register.html")
