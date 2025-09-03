from flask import Blueprint, render_template, request, redirect, url_for
from app import db   # app.py에서 선언한 db 객체 가져오기

views_bp = Blueprint('views', __name__)

# 임시 데이터 저장 (목표)
dummy = {"goal_amount": None}

@views_bp.route('/')
def home():
    return render_template('base.html')

@views_bp.route('/mypage')
def go_mypage():
    return render_template(
        "mypage.html",
        activate_tab="mypage",
        baekjoon_id="yyy",
        today_amount=2,
        total_amount=10,
        tier="Ruby",
        goal_amount=dummy.get("goal_amount"),
        Ruby=0, Diamond=0, Platinum=0, Gold=0, Silver=0, Bronze=0
    )

@views_bp.route("/reviews")
def go_reviews():
    return render_template("reviews.html", activate_tab="reviews")

@views_bp.route("/rank")
def go_rank():
    return render_template("rank.html", activate_tab="rank")

@views_bp.route("/set_goal", methods=['POST'])
def submit_goal():
    dummy["goal_amount"] = request.form['goal_amount']
    return redirect(url_for("views.go_mypage"))

@views_bp.route("/reset_goal")
def reset_goal():
    dummy["goal_amount"] = None
    return redirect(url_for("views.go_mypage"))
