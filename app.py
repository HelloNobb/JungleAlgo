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
from pymongo.errors import CollectionInvalid
import threading
import os
app = Flask(__name__)

client = MongoClient('localhost', 27017)
db = client.jungle_algo

users_collection = db.users

# 컬렉션 정의 및 생성/인덱스
solved_log = db['solved_log']
try:
    db.create_collection('solved_log')
except CollectionInvalid:
    pass

# 인덱스(생성만 해도 컬렉션이 만들어짐)
solved_log.create_index([('baekjoon_id', 1), ('problem_id', 1)], unique=True)
solved_log.create_index([('baekjoon_id', 1), ('solved_at', -1)])
solved_log.create_index([('baekjoon_id', 1), ('tier', 1)])



@app.route('/')
def home():
   return render_template('base.html')

backjun_id = 'yoon0'  # 현재 하드코딩된 값


@app.route('/api/register', methods=["POST"])
def register():
    try:
        # TODO : 사용자 정보 가져와서 url에 동적으로 입력해줘야 함.
        # data = request.get_json()
        # backjun_id = data.get('backjun_id')
        
        
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
        backjun_rank = result.get('등수')
        backjun_correct = result.get('맞은 문제')
        backjun_failed = result.get('시도했지만 맞지 못한 문제')

        # 랭크 여부 확인 굳이 필요할지? 없으면 false로 설정해도 될듯?
        # if not backjun_rank:
        #     return jsonify({
        #         'success': False,
        #         'message': '백준 등수 정보를 찾을 수 없습니다.'
        #     }), 400

        user_data = {
            'backjun_id': backjun_id,
            'rank': int(backjun_rank),
            'backjun_correct': 0,
            'backjun_failed': 0,
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
                'rank': int(backjun_rank),
                'backjun_correct': backjun_correct,
                'backjun_failed': backjun_failed
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
    tier_counts = list(solved_log.aggregate([
        {'$match': {'baekjoon_id': bj}},
        {'$group': {'_id': '$tier', 'count': {'$sum': 1}}},
        {'$sort': {'_id': 1}}
    ]))

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
                'tier_counts': tier_counts
            }
        }
    })


# 사용자 데이터 업데이트 구현
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; JungleAlgoBot/1.0)'}

def kst_today_range():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    end_kst = start_kst + timedelta(days=1)
    return start_kst, end_kst

def fetch_status_html(user_id):
    url = f'https://www.acmicpc.net/status?problem_id=&user_id={user_id}&language_id=-1&result_id=-1'
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return None
    return resp.text

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

def upsert_today_submissions(user_id, items):
    updated = 0
    for it in items:
        # 날짜별 기록을 원하면 unique를 (baekjoon_id, problem_id, date)로 운영하세요.
        # 현재 인덱스가 (baekjoon_id, problem_id)인 경우에는 같은 문제는 하루 1회만 유지됨.
        solved_log.update_one(
            {'baekjoon_id': user_id, 'problem_id': it['problem_id']},
            {'$setOnInsert': {'title': None, 'difficulty': None},
             '$set': {
                 'date': it['date_kst'],
                 'solved_at': it['solved_at_utc'],
                 'result': 'correct',
                 'review': False
             },
             '$inc': {'submission_count': 1}},
            upsert=True
        )
        updated += 1
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
    users_collection.update_one(
        {'backjun_id': user_id},
        {'$set': {
            'rank': data.get('rank'),
            'backjun_correct': data.get('backjun_correct'),
            'backjun_failed': data.get('backjun_failed'),
            'updated_at': datetime.utcnow()
        }}
    )
    return True


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