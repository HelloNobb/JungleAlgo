# blueprint - 마이페이지>목표설정여부에따라 box다르게 설정하기
from flask import Blueprint, render_template

# 'views'라는 이름을 가진 블루프린트 생성
views_bp = Blueprint('views', __name__)

# @views_bp.route('/')
# def home():
#     return render_template('home.html')

# @views_bp.route('/about')
# def about():
#     return render_template('about.html')
