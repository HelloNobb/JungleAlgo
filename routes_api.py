#JSON API 라우트
import pytz
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from app import db   # app.py에서 선언한 db 객체 가져오기

api_bp = Blueprint('api', __name__)

users_collection = db.users
solved_log = db['solved_log']

# 회원가입 API 예시
@api_bp.route('/register', methods=["POST"])
def register():
    backjun_id = request.json.get("backjun_id")
    if not backjun_id:
        return jsonify({'success': False, 'message': 'ID가 필요합니다'}), 400

    existing_user = users_collection.find_one({"backjun_id": backjun_id})
    if existing_user:
        return jsonify({'success': False, 'message': '이미 존재하는 사용자'}), 409

    user_data = {
        'backjun_id': backjun_id,
        'rank': None,
        'backjun_correct': 0,
        'backjun_failed': 0,
        'today_goal': 0,
        'created_at': datetime.now()
    }
    users_collection.insert_one(user_data)

    return jsonify({'success': True, 'user_data': user_data})

# 프로필 조회
@api_bp.route('/profile/<bj>', methods=['GET'])
def read_profile(bj):
    profile = users_collection.find_one({'backjun_id': bj}, {'_id': 0})
    if not profile:
        return jsonify({'success': False, 'message': '사용자 없음'}), 404

    def today_range_kst():
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        end_kst = start_kst + timedelta(days=1)
        return start_kst.astimezone(pytz.UTC), end_kst.astimezone(pytz.UTC)

    start_utc, end_utc = today_range_kst()
    total = solved_log.count_documents({'baekjoon_id': bj})
    today = solved_log.count_documents({'baekjoon_id': bj, 'solved_at': {'$gte': start_utc, '$lt': end_utc}})

    return jsonify({
        'success': True,
        'data': {
            'profile': profile,
            'stats': {'total': total, 'today': today}
        }
    })

# 주간 통계
@api_bp.route('/stats/weekly/<user_id>', methods=['GET'])
def weekly_stats(user_id):
    try:
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        days_since_sunday = (now_kst.weekday() + 1) % 7
        start_of_week_kst = (now_kst - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)

        def fmt(d): return d.strftime('%Y-%m-%d')
        start_date_str = fmt(start_of_week_kst)
        last_inclusive_date_str = fmt(start_of_week_kst + timedelta(days=6))

        pipeline = [
            {'$match': {'baekjoon_id': user_id, 'date': {'$gte': start_date_str, '$lte': last_inclusive_date_str}}},
            {'$group': {'_id': '$date', 'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]
        rows = list(solved_log.aggregate(pipeline))
        date_to_count = {r['_id']: r['count'] for r in rows}

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
