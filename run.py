from app import create_app, db
from flask import Flask, jsonify

app = create_app()


@app.route('/')
def index():
    return jsonify({"message": "CloudifyShare Flask app running successfully!"}), 200

@app.route('/api/health')
def health():
    return "ok", 200

if __name__ == "__main__":
    with app.app_context():
        # db.drop_all()
        db.create_all()
    app.run(host="0.0.0.0", port=80, debug=True)
