from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///results-test.db'
db = SQLAlchemy(app)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    group_id = db.Column(db.Integer, nullable=False)
    response = db.Column(db.String(20), nullable=False)
    dataset = db.Column(db.String(50), nullable=False)
    images = db.Column(db.Text, nullable=False)

with app.app_context():
    results = Result.query.all()
    for result in results:
        print(f"ID: {result.id}, User ID: {result.user_id}, Group ID: {result.group_id}, Response: {result.response}, Dataset: {result.dataset}, Images: {result.images}")
