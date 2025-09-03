#app.py
from flask import Flask, app, render_template, request, jsonify, redirect, url_for
from flask_jwt_extended import *
from pymongo import MongoClient
from datetime import timedelta
from flask_bcrypt import Bcrypt

# pip install flask-bcrypt
# pip install flask-jwt-extended

app = Flask(__name__)

#더미값
dummy = {"goal_amount":None, "today_amount":0, "total_amount" : 100, "user_id":"HJ"}

@app.route('/')
def home():
    #00:00이후 목표설정했는지 확인, 달성했는지 확인
    return redirect(url_for("go_mypage"))

@app.route("/reviews")
def go_reviews():
	return render_template("reviews.html", activate_tab="reviews")

@app.route("/mypage")
def go_mypage(): #진자에서 mypage받아서 쓰는것
	return render_template("mypage.html", activate_tab="mypage", )

@app.route("/rank")
def go_rank():
	return render_template("rank.html", activate_tab="rank")

@app.get("/")
def goalboard():
    return render_template(
		goal_amount = "goal_amount"
	)

@app.route("/set_goal", methods=['POST'])
def submit_goal():
    dummy["goal_amount"] = request.form['goal_amount']

@app.route("/reset_goal")
def reset_goal():
    dummy["goal_amount"] = None
    return redirect(url_for(""))
    


if __name__ == '__main__':
	app.run(host = '0.0.0.0',
					port = 5002, 
					debug = True)