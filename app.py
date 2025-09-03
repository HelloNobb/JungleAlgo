from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from urllib.parse import _ResultMixinBytes
import requests
import json
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient
from pymongo import DESCENDING
from pymongo.errors import CollectionInvalid
import threading
import os

app = Flask(__name__)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
#db 연결
client = MongoClient('localhost', 27017)
db = client.jungle_algo

users_collection = db.users

# 컬렉션 정의 및 생성/인덱스
solved_log = db['solved_log']
# try:
#     db.create_collection('solved_log')
# except CollectionInvalid:
#     pass

# 인덱스(생성만 해도 컬렉션이 만들어짐)
#solved_log.create_index([('baekjoon_id', 1), ('problem_id', 1)], unique=True)
# solved_log.create_index([('baekjoon_id', 1), ('solved_at', -1)])
# solved_log.create_index([('baekjoon_id', 1), ('tier', 1)])

app.config['JWT_SECRET_KEY'] = "myAlgorithmJWT"

# 홈/로그인 ============= ================
@app.route('/')
def home():
    return render_template('login.html')

@app.route('/loginpage')
def loginpage():
    return render_template('login.html')

@app.route('/loginpage/login', methods=["POST"])
def login():
    #data: {userid_give: userid, password_give: password}, // data라는 이름으로 userid와 password를 줄게
    id_receive = request.form['userid_give']  # 클라이언트로부터 id를 받는 부분
    password_receive = request.form['password_give']  # 클라이언트로부터 비밀번호를 받는 부분
    
    memo = db.memos.find_one({"id": id_receive})
    if memo and bcrypt.check_password_hash(memo['hashed_password'], password_receive):
        # 로그인 성공 → JWT 발급
        access_token = create_access_token(identity=id_receive, expires_delta=timedelta(minutes=30))
        # JSON 응답 대신 마이페이지로 리다이렉트 (쿠키에 저장하거나 프론트에서 처리)
        return redirect(url_for("mypage"))
    return jsonify({"result": "fail", "msg": "아이디 또는 비밀번호 오류"})

# 회원가입 ============= ================

@app.route('/signuppage')
def signuppage():
    return render_template('signup.html')

@app.route("/signuppage/checkid", methods=["POST"])
def checkid():
    id_receive = request.form['userid_give']  # 클라이언트로부터 id를 받는 부분
    
    memo=db.memos.find_one({"id": id_receive})
    if(memo):
        return jsonify({"result": "fail", "msg": "이미 존재하는 아이디입니다."})
    return jsonify({"result": "success"})

# 마이페이지 ============= ================
@app.route('/mypage')
@jwt_required()   # 로그인한 사람만 접근 허용
def mypage():
    c_user = get_jwt_identity()
    if not c_user:
        return redirect(url_for("loginpage"))
    
    res = db.users.find_one({"backjun_id":c_user})
    return render_template( ### db에서 불러오기
		"mypage.html",
		activate_tab="mypage",
		baekjoon_id=c_user,
		today_amount=parse_status_rows_today(c_user).len(),
		total_amount=res.backjun_correct,
		tier="Ruby",
		goal_amount=None,
		Ruby=0, Diamond=0, Platinum=0, Gold=0, Silver=0, Bronze=0
	)
def fetch_status_html(user_id):
    url = f'https://www.acmicpc.net/status?problem_id=&user_id={user_id}&language_id=-1&result_id=-1'
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return None
    return resp.text

# 해당 유저의 오늘 푼 문제에 대한 ID, 시간, 날짜 데이터 파싱
def parse_status_rows_today(user_id):
    html = fetch_status_html(user_id)
    if not html:
        return []

    start_kst, end_kst = kst_today_range()
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('#status-table') or soup.select_one('table#status-table') or soup.select_one('table.table') or soup.select_one('table')
    if not table:
        return []

    items = []
    for tr in table.select('tr'):
        tds = tr.find_all('td')
        if not tds:
            continue

        # 문제 ID: 문제 링크를 직접 탐색
        problem_link = tr.select_one('a[href^="/problem/"]')
        if not problem_link:
            continue
        problem_id_text = problem_link.get_text(strip=True)
        if not problem_id_text.isdigit():
            continue
        problem_id = int(problem_id_text)

        # 결과 텍스트: 행 전체에서 텍스트 검색 (맞았습니다!! 등 변형 대응)
        row_text = tr.get_text(" ", strip=True)
        if '맞았습니다' not in row_text:
            continue

        # 제출 시간: .real-time-update 가진 요소에서 data-timestamp 추출 (a/span 대응)
        ts_el = tr.select_one('.real-time-update')
        ts = ts_el.get('data-timestamp') if ts_el else None
        if not ts or not str(ts).isdigit():
            # 보조: 행의 어떤 요소라도 data-timestamp를 갖고 있으면 사용
            any_ts_el = tr.select_one('[data-timestamp]')
            ts = any_ts_el.get('data-timestamp') if any_ts_el else None
        if not ts or not str(ts).isdigit():
            continue

        kst = pytz.timezone('Asia/Seoul')
        utc_dt = datetime.utcfromtimestamp(int(ts)).replace(tzinfo=pytz.UTC)
        kst_dt = utc_dt.astimezone(kst)

        # 오늘(KST)만
        if not (start_kst <= kst_dt < end_kst):
            continue

        items.append({
            'problem_id': problem_id,
            'solved_at_utc': utc_dt,
            'date_kst': kst_dt.strftime('%Y-%m-%d')
        })
    return items