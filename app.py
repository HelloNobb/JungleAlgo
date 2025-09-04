from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from pymongo import MongoClient, DESCENDING
from pymongo.errors import CollectionInvalid
from urllib.parse import _ResultMixinBytes
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests
import json
import re
import time
import pytz
import threading
import os
## views.py (목표설정박스 동적변경용)
from views import views_bp

app = Flask(__name__)
app.register_blueprint(views_bp) # 블루프린트를 flask앱에 등록
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
#db 연결
client = MongoClient('localhost', 27017)
db = client.jungle_algo


# 컬렉션 정의 및 생성/인덱스
solved_log = db['solved_log']
users_collection = db['users']

# try:
#     db.create_collection('solved_log')
# except CollectionInvalid:
#     pass

# 인덱스(생성만 해도 컬렉션이 만들어짐)
solved_log.create_index([('baekjoon_id', 1), ('problem_id', 1)], unique=True)
solved_log.create_index([('baekjoon_id', 1), ('solved_at', -1)])
solved_log.create_index([('baekjoon_id', 1), ('tier', 1)])

#app.config['JWT_SECRET_KEY'] = "myAlgorithmJWT"
app.config.update(
    DEBUG=True,
    # JWT에만 사용될 시크릿 키
    JWT_SECRET_KEY="myAlgorithmJWT",
    # bcrypt의 난이도 설정
    BCRYPT_LEVEL=10,
    # JWT 토큰 위치 설정 (헤더와 쿠키 모두 허용)
    JWT_TOKEN_LOCATION=['headers', 'cookies'],
    JWT_ACCESS_COOKIE_NAME='access_token_cookie',
    JWT_COOKIE_CSRF_PROTECT=False
)

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
        # JSON 응답으로 JWT 토큰 반환
        return jsonify({"result": "success", "access_token": access_token})
    return jsonify({"result": "fail", "msg": "아이디 또는 비밀번호 오류"})

# 회원가입 =============================

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

@app.route("/signuppage/signup", methods=["POST"])
def signup():
    #                data: {userid_give: userid, useremail_give: useremail, password_give: password}, // data라는 이름으로 userid와 useremail, useremailadress, password를 줄게
    # 1. 클라이언트로부터 데이터를 받기
    id_receive = request.form['userid_give']  # 클라이언트로부터 id를 받는 부분
    email_receive = request.form['useremail_give']  # 클라이언트로부터 이메일을 받는 부분
    password_receive = request.form['password_give']  # 클라이언트로부터 비밀번호를 받는 부분
    hashed_password = bcrypt.generate_password_hash(password_receive)
    # 보안을 위해 password_receive를 사용 후 삭제합니다.
    del password_receive
    
    memos = {'id':id_receive, 'email': email_receive, 'hashed_password': hashed_password}

    # 2. mongoDB에 데이터를 넣기
    db.memos.insert_one(memos)

    return jsonify({'result': 'success'})

# 마이페이지 =============================
@app.route('/mypage')
@jwt_required()
def mypage():
    # JWT 토큰 검증
    c_user = get_jwt_identity()
    if not c_user:
        return redirect(url_for("loginpage"))
    
    user_info = users_collection.find_one({"backjun_id": c_user})
    #today
    kst = pytz.timezone('Asia/Seoul')
    today_str = datetime.now(kst).strftime("%Y-%m-%d")

    # goal_amount 기본값 설정
    goal_amount = None
    
    if user_info and "today_goal" in user_info:
        tg = user_info["today_goal"]
        if tg.get("date") == today_str:
            goal_amount = tg.get("goal_amount")
    
    # 오늘 푼 문제 수 계산
    today_problems = parse_status_rows_today(c_user)
    today_amount = len(today_problems) if today_problems else 0
    
    # 총 문제 수 (백준 정보가 있으면 사용, 없으면 0)
    total_amount = res.get('backjun_correct', 0) if res else 0
    
    # difficulty_counts 가져오기
    difficulty_counts = res.get('difficulty_counts', {
        'Bronze': 0,
        'Silver': 0,
        'Gold': 0,
        'Platinum': 0,
        'Diamond': 0
    }) if res else {
        'Bronze': 0,
        'Silver': 0,
        'Gold': 0,
        'Platinum': 0,
        'Diamond': 0
    }
    

    return render_template(
		"mypage.html",
		activate_tab="mypage",
		baekjoon_id=c_user,
		today_amount=today_amount,
		total_amount="?",
		tier="Ruby",
		goal_amount=None,
		difficulty_counts=difficulty_counts,
		Ruby=difficulty_counts.get('Ruby', 0), 
		Diamond=difficulty_counts.get('Diamond', 0), 
		Platinum=difficulty_counts.get('Platinum', 0), 
		Gold=difficulty_counts.get('Gold', 0), 
		Silver=difficulty_counts.get('Silver', 0), 
		Bronze=difficulty_counts.get('Bronze', 0)
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

@app.route('/rank')
def rank():
    top3 = list(db.users.find({}, {'_id': 0, 'backjun_id': 1, 'backjun_correct': 1})
            .sort('backjun_correct', DESCENDING).limit(3))
    for idx, user in enumerate(top3, start=1):
        user['rank'] = idx
    return render_template("rank.html", top3=top3)

## input > pot/get 받기============================
@app.route('/set_goal', methods=["POST"])
@jwt_required()
def set_goal():
    c_user = get_jwt_identity()
    if not c_user:
        return redirect(url_for("loginpage"))
    ## form 데이터 꺼내기
    goal_amount = request.form.get("goal_amount", type=int)
    ## 오늘날짜
    kst = pytz.timezone('Asia/Seoul')
    today_str = datetime.now(kst).strftime("%Y-%m-%d")
    ## db 저장
    users_collection.update_one(
        {"backjun_id": c_user},
        {"$set":{"today_goal":{"date":today_str, "goal_amount":goal_amount}}},
        upsert = True
    )
    
    return redirect(url_for("mypage"))
    
## db에서 데이터 가져오는 함수들 ()==================
def get_today_amount(user):
    user = get_jwt_identity()
    if not user:
        return redirect(url_for("loginpage"))
    # 회원 맞으면
    

    
@app.route("/reviews")
def reviews():
    return render_template("reviews.html", activate_tab="reviews")

# 해당 유저의 오늘 푼 문제에 대한 ID, 시간, 날짜 데이터 파싱>>>> return items
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


# 회원가입 =============== ===============
@app.route('/api/register', methods=["POST"])
def register():
    try:
        # 사용자 정보 가져오기
        data = request.get_json()
        backjun_id = data.get('backjun_id')
        
        if not backjun_id:
            return jsonify({
                'success': False,
                'message': '백준 ID가 필요합니다.'
            }), 400
        
        # 1. 먼저 중복 체크
        existing_user = users_collection.find_one({"backjun_id": backjun_id})
        if existing_user:
            return jsonify({
                'success': False,
                'message': f'이미 등록된 사용자입니다. (ID: {backjun_id})',
                'error_code': 'DUPLICATE_USER'
            }), 409  # 409 Conflict
        
        headers = {'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}
        response = requests.get(f'https://www.acmicpc.net/user/{backjun_id}', headers=headers)
        
        if response.status_code != 200:
            return jsonify({
                'success': False,
                'message': f'백준 사이트에서 사용자 정보를 가져올 수 없습니다. (상태코드: {response.status_code})'
            }), 400
        
        soup = BeautifulSoup(response.text, 'html.parser')
        stats_table = soup.select_one('#statics > tbody')
        
        # # 디버깅을 위한 로그
        # print(f"백준 ID: {backjun_id}")
        # print(f"응답 상태코드: {response.status_code}")
        # print(f"stats_table 존재 여부: {stats_table is not None}")
        
        if not stats_table:
            return jsonify({
                'success': False,
                'message': '백준 온라인 저지에서 사용자 정보를 찾을 수 없습니다.'
            }), 404
        
        # 테이블 형식의 데이터를 가공해서 객체 형태로 변환
        result = {}
        rows = stats_table.select('tbody tr')

        for row in rows:
               th = row.select_one('th')
               td = row.select_one('td')
               
               if th and td:
                   key = th.get_text(strip=True)
                   value = td.get_text(strip=True)
                   result[key] = value

        # 사용자 데이터 저장
        backjun_rank = result.get('등수', '0')
        backjun_correct = result.get('맞은 문제', '0')
        backjun_failed = result.get('시도했지만 맞지 못한 문제', '0')

        # 백준에서 가져온 데이터를 숫자로 변환 (콤마 제거)
        try:
            backjun_rank = int(backjun_rank.replace(',', '')) if backjun_rank else 0
            backjun_correct = int(backjun_correct.replace(',', '')) if backjun_correct else 0
            backjun_failed = int(backjun_failed.replace(',', '')) if backjun_failed else 0
        except (ValueError, AttributeError):
            backjun_rank = 0
            backjun_correct = 0
            backjun_failed = 0

        # 기존 해결한 문제들을 solved_log에 추가
        print(f"Fetching solved problems for {backjun_id}...")
        solved_problem_ids = fetch_user_solved_problems(backjun_id)
        
        if solved_problem_ids:
            print(f"Importing {len(solved_problem_ids)} solved problems...")
            imported_count = import_user_solved_problems(backjun_id, solved_problem_ids)
            print(f"Imported {imported_count} problems to solved_log")
        
        # total 값 계산 (solved_log에서 해당 사용자의 전체 제출 개수)
        total = solved_log.count_documents({'baekjoon_id': backjun_id})

        # difficulty_counts 계산 (solved_log에서 집계)
        difficulty_counts_agg = list(solved_log.aggregate([
            {'$match': {'baekjoon_id': backjun_id}},
            {'$group': {'_id': '$difficulty', 'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]))
        
        # difficulty_counts를 객체 형태로 변환
        difficulty_counts = {
            'Bronze': 0,
            'Silver': 0,
            'Gold': 0,
            'Platinum': 0,
            'Diamond': 0
        }
        
        for item in difficulty_counts_agg:
            difficulty = item['_id']
            count = item['count']
            if difficulty in difficulty_counts:
                difficulty_counts[difficulty] = count

        # 랭크 여부 확인 굳이 필요할지? 없으면 false로 설정해도 될듯?
        # if not backjun_rank:
        #     return jsonify({
        #         'success': False,
        #         'message': '백준 등수 정보를 찾을 수 없습니다.'
        #     }), 400

        user_data = {
            'backjun_id': backjun_id,
            'rank': backjun_rank,
            'backjun_correct': backjun_correct,
            'backjun_failed': backjun_failed,
            'total': total,
            'difficulty_counts': difficulty_counts,
            'today_goal': 0,
            'created_at': datetime.now()
        }

        # 2. 사용자 데이터 저장
        addUser = users_collection.insert_one(user_data)

        return jsonify({
            'success': True,
            'message': '데이터가 성공적으로 저장되었습니다',
            'inserted_id': str(addUser.inserted_id),
            'user_data': {
                'backjun_id': backjun_id,
                'rank': backjun_rank,
                'backjun_correct': backjun_correct,
                'backjun_failed': backjun_failed,
                'total': total
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'데이터 저장 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/api/profile/<bj>', methods=['GET'])
def readProfile(bj):
    # 사용자 프로필 조회
    profile = users_collection.find_one({'backjun_id': bj}, {'_id': 0})
    if not profile:
        return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': '사용자 없음'}}), 404

    # 오늘의 범위(KST)
    def today_range_kst():
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        end_kst = start_kst + timedelta(days=1)
        return start_kst.astimezone(pytz.UTC), end_kst.astimezone(pytz.UTC)

    start_utc, end_utc = today_range_kst()

    # solved_log 집계 (주의: solved_log는 baekjoon_id 필드 사용 가정)
    total = solved_log.count_documents({'baekjoon_id': bj})
    today = solved_log.count_documents({'baekjoon_id': bj, 'solved_at': {'$gte': start_utc, '$lt': end_utc}})
    agg = list(solved_log.aggregate([
        {'$match': {'baekjoon_id': bj}},
        {'$group': {'_id': None, 'review_point': {'$sum': '$review_point'}}}
    ]))
    review_point = agg[0]['review_point'] if agg else 0
    # users 컬렉션에서 difficulty_counts 가져오기 (성능 개선)
    user_doc = users_collection.find_one({'backjun_id': bj}, {'difficulty_counts': 1})
    difficulty_counts = user_doc.get('difficulty_counts', {
        'Bronze': 0,
        'Silver': 0,
        'Gold': 0,
        'Platinum': 0,
        'Diamond': 0
    }) if user_doc else {
        'Bronze': 0,
        'Silver': 0,
        'Gold': 0,
        'Platinum': 0,
        'Diamond': 0
    }

    # 간단 랭킹
    rank_cursor = users_collection.find({}, {'_id': 0, 'backjun_id': 1, 'problem_point': 1, 'review_point': 1})
    sorted_users = sorted(rank_cursor, key=lambda u: (u.get('problem_point', 0), u.get('review_point', 0)), reverse=True)
    rank = next((i + 1 for i, u in enumerate(sorted_users) if u.get('backjun_id') == bj), None)

    return jsonify({
        'success': True,
        'data': {
            'profile': profile,
            'stats': {
                'total': total,
                'today': today,
                'review_point': review_point,
                'rank': rank,
                'difficulty_counts': difficulty_counts
            }
        }
    })


# 사용자 데이터 업데이트 구현
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; JungleAlgoBot/1.0)'}

    # 오늘 시간에 대한 기준을 생성함.

def kst_today_range():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    end_kst = start_kst + timedelta(days=1)
    return start_kst, end_kst


# 이번 주(일요일~토요일) 일별 풀이 수 집계 API
@app.route('/api/stats/weekly/<user_id>', methods=['GET'])
def weekly_stats(user_id):
    try:
        # 1) KST 기준 오늘, 이번 주 일요일~토요일 계산
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        days_since_sunday = (now_kst.weekday() + 1) % 7  # Mon=0..Sun=6 → Sun=0
        start_of_week_kst = (now_kst - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week_kst = start_of_week_kst + timedelta(days=7)  # 다음 주 일요일 00:00 (exclusive)

        def fmt(d):
            return d.strftime('%Y-%m-%d')
        start_date_str = fmt(start_of_week_kst)
        last_inclusive_date_str = fmt(start_of_week_kst + timedelta(days=6))

        # 3) MongoDB 집계: 해당 주간 범위 매칭 후 날짜별 그룹
        pipeline = [
            {'$match': {
                'baekjoon_id': user_id,
                'date': {'$gte': start_date_str, '$lte': last_inclusive_date_str}
            }},
            {'$group': {'_id': '$date', 'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]
        rows = list(solved_log.aggregate(pipeline))
        date_to_count = {r['_id']: r['count'] for r in rows}

        # 4) 누락된 날짜는 0으로 채움 (일요일~토요일 7일)
        daily = []
        for i in range(7):
            d = start_of_week_kst + timedelta(days=i)
            ds = fmt(d)
            daily.append({'date': ds, 'count': int(date_to_count.get(ds, 0))})

        return jsonify({
            'success': True,
            'user_id': user_id,
            'range': {'start': start_date_str, 'end': last_inclusive_date_str},
            'daily': daily
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 오늘 푼 문제에 대한 데이터를 가져올 수 있는 url 
def fetch_status_html(user_id):
    url = f'https://www.acmicpc.net/status?problem_id=&user_id={user_id}&language_id=-1&result_id=-1'
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return None
    return resp.text



def get_problem_difficulty(problem_id):
    try:
        url = f'https://solved.ac/api/v3/problem/show?problemId={problem_id}'
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; JungleAlgoBot/1.0)'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        level = data.get('level', 0)
        
        # solved.ac 레벨을 단순화된 난이도로 매핑
        if level <= 5:
            return 'Bronze'
        elif level <= 10:
            return 'Silver'
        elif level <= 15:
            return 'Gold'
        elif level <= 20:
            return 'Platinum'
        elif level <= 25:
            return 'Diamond'
        else:
            return 'Ruby'
    except Exception:
        return None


def fetch_user_solved_problems(user_id):
    """백준에서 사용자가 해결한 문제 목록을 가져옵니다."""
    try:
        url = f'https://solved.ac/api/v3/search/problem'
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; JungleAlgoBot/1.0)'}
        
        # solved.ac API를 사용하여 사용자가 해결한 문제 목록 가져오기
        params = {
            'query': f'solved_by:{user_id}',
            'sort': 'solved',
            'direction': 'desc',
            'page': 1
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to fetch solved problems for {user_id}: {response.status_code}")
            return []
            
        data = response.json()
        problems = data.get('items', [])
        
        # 문제 ID만 추출
        problem_ids = [problem.get('problemId') for problem in problems if problem.get('problemId')]
        
        return problem_ids
        
    except Exception as e:
        print(f"Error fetching solved problems for {user_id}: {e}")
        return []


def import_user_solved_problems(user_id, problem_ids):
    """사용자의 기존 해결한 문제들을 solved_log에 추가합니다."""
    imported_count = 0
    
    for problem_id in problem_ids:
        try:
            # 문제 난이도 가져오기
            difficulty = get_problem_difficulty(problem_id)
            
            # solved_log에 추가 (중복 방지를 위해 upsert 사용)
            solved_log.update_one(
                {'baekjoon_id': user_id, 'problem_id': problem_id},
                {'$setOnInsert': {
                    'title': None,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'solved_at': datetime.utcnow(),
                    'result': 'correct',
                    'review': False,
                    'difficulty': difficulty,
                    'submission_count': 1
                }},
                upsert=True
            )
            
            imported_count += 1
            time.sleep(0.1)  # API 호출 제한 방지
            
        except Exception as e:
            print(f"Error importing problem {problem_id} for {user_id}: {e}")
            continue
    
    return imported_count

def upsert_today_submissions(user_id, items):
    updated = 0
    for it in items:
        # 문제 난이도 정보 가져오기
        difficulty = get_problem_difficulty(it['problem_id'])
        
        # 날짜별 기록을 원하면 unique를 (baekjoon_id, problem_id, date)로 운영하세요.
        # 현재 인덱스가 (baekjoon_id, problem_id)인 경우에는 같은 문제는 하루 1회만 유지됨.
        solved_log.update_one(
            {'baekjoon_id': user_id, 'problem_id': it['problem_id']},
            {'$setOnInsert': {'title': None},
             '$set': {
                 'date': it['date_kst'],
                 'solved_at': it['solved_at_utc'],
                 'result': 'correct',
                 'review': False,
                 'difficulty': difficulty
             },
             '$inc': {'submission_count': 1}},
            upsert=True
        )
        updated += 1
        time.sleep(0.1)  
    return updated

@app.route('/api/backjun/update_status/<user_id>', methods=['POST'])
def update_status_user(user_id):
    try:
        items = parse_status_rows_today(user_id)
        cnt = upsert_today_submissions(user_id, items)
        return jsonify({'success': True, 'user_id': user_id, 'updated': cnt})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/backjun/update_status_all', methods=['POST'])
def update_status_all():
    try:
        total = update_all_users_once()
        return jsonify({'success': True, 'updated_total': total})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def update_all_users_once():
    users = users_collection.find({}, {'_id': 0, 'backjun_id': 1})
    total = 0
    for u in users:
        uid = u.get('backjun_id')
        if not uid:
            continue
        items = parse_status_rows_today(uid)
        total += upsert_today_submissions(uid, items)
        time.sleep(1.0)  # 과도한 요청 방지
    return total


# --- 프로필(사용자 정보) 업데이트 ---
def _parse_int_safe(text):
    if text is None:
        return None
    try:
        # 쉼표, 공백 제거 후 정수 변환
        return int(str(text).replace(',', '').strip())
    except Exception:
        return None

def fetch_user_profile(user_id):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}
    resp = requests.get(f'https://www.acmicpc.net/user/{user_id}', headers=headers, timeout=10)
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, 'html.parser')
    stats_table = soup.select_one('#statics > tbody')
    if not stats_table:
        return None
    result = {}
    rows = stats_table.select('tr')
    for row in rows:
        th = row.select_one('th')
        td = row.select_one('td')
        if th and td:
            key = th.get_text(strip=True)
            value = td.get_text(strip=True)
            result[key] = value
    # register에서 저장했던 필드들 동일 처리
    rank = _parse_int_safe(result.get('등수'))
    backjun_correct = _parse_int_safe(result.get('맞은 문제'))
    backjun_failed = _parse_int_safe(result.get('시도했지만 맞지 못한 문제'))
    return {
        'rank': rank,
        'backjun_correct': backjun_correct,
        'backjun_failed': backjun_failed
    }

def update_user_profile(user_id):
    data = fetch_user_profile(user_id)
    if not data:
        return False
    # total 값 계산 (예: solved_log에서 해당 사용자의 전체 제출 개수)
    total = solved_log.count_documents({'baekjoon_id': user_id})
    
    # difficulty_counts 계산 (solved_log에서 집계)
    difficulty_counts = list(solved_log.aggregate([
        {'$match': {'baekjoon_id': user_id}},
        {'$group': {'_id': '$difficulty', 'count': {'$sum': 1}}},
        {'$sort': {'_id': 1}}
    ]))
    
    difficulty_dict = {
        'Bronze': 0,
        'Silver': 0,
        'Gold': 0,
        'Platinum': 0,
        'Diamond': 0
    }
    
    for item in difficulty_counts:
        difficulty = item['_id']
        count = item['count']
        if difficulty in difficulty_dict:
            difficulty_dict[difficulty] = count
    
    users_collection.update_one(
        {'backjun_id': user_id},
        {'$set': {
            'rank': data.get('rank'),
            'backjun_correct': data.get('backjun_correct'),
            'backjun_failed': data.get('backjun_failed'),
            'total': total,
            'difficulty_counts': difficulty_dict,
            'updated_at': datetime.utcnow()
        }}
    )
    return True


def update_user_difficulty_count(user_id, difficulty):
    """새 문제 제출 시 해당 사용자의 difficulty_counts 업데이트"""
    if not difficulty:
        return
    
    users_collection.update_one(
        {'backjun_id': user_id},
        {'$inc': {f'difficulty_counts.{difficulty}': 1}}
    )


def update_all_users_profile_once():
    users = users_collection.find({}, {'_id': 0, 'backjun_id': 1})
    updated = 0
    for u in users:
        uid = u.get('backjun_id')
        if not uid:
            continue
        if update_user_profile(uid):
            updated += 1
        time.sleep(1.0)
    return updated


@app.route('/api/backjun/update_users_profile_all', methods=['POST'])
def update_users_profile_all():
    try:
        cnt = update_all_users_profile_once()
        return jsonify({'success': True, 'updated_profiles': cnt})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


def seconds_until_next_kst_hour():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    next_hour = (now_kst.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return max(1, int((next_hour - now_kst).total_seconds()))


_scheduler_started = False


def _scheduler_loop():
    while True:
        try:
            sleep_sec = seconds_until_next_kst_hour()
            time.sleep(sleep_sec)
            # 1) 모든 유저 프로필 최신화
            update_all_users_profile_once()
            # 2) 오늘 푼 문제 집계/업서트
            update_all_users_once()
        except Exception:
            # 에러는 무시하고 다음 라운드로 진행
            time.sleep(5)


def start_scheduler_once():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    t = threading.Thread(target=_scheduler_loop, name='hourly-updater', daemon=True)
    t.start()


if __name__ == '__main__':
    # 재로더로 인한 중복 실행 방지
    if not os.environ.get('WERKZEUG_RUN_MAIN') or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_scheduler_once()
    app.run('0.0.0.0', port=5001, debug=True)