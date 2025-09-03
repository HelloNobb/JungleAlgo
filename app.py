from urllib.parse import _ResultMixinBytes
import requests
import json
import re

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient
app = Flask(__name__)

client = MongoClient('localhost', 27017)
db = client.jungle_algo

users_collection = db.users
solvedLog_collevtion = db.sovled_LOG

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
            'backjun_correct': backjun_correct,
            'backjun_failed': backjun_failed,
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
    user = users_collection.find_one({'backjun_id': bj}, {'_id':0})
    if not user:
        return jsonify({'success': False, 'error': {'code':'NOT_FOUND','message':'사용자 없음'}}), 404

    def today_range_kst():
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        end_kst = start_kst + timedelta(days=1)
        # UTC로 변환
        return start_kst.astimezone(pytz.UTC), end_kst.astimezone(pytz.UTC)

    start_utc, end_utc = today_range_kst()
    total = solvedLog_collevtion.count_documents({'baekjoon_id': bj})
    today = solvedLog_collevtion.count_documents({'baekjoon_id': bj, 'solved_at': {'$gte': start_utc, '$lt': end_utc}})
    agg = list(solvedLog_collevtion.aggregate([
        {'$match': {'baekjoon_id': bj}},
        {'$group': {'_id': None, 'review_point': {'$sum': '$review_point'}}}
    ]))
    review_point = agg[0]['review_point'] if agg else 0
    tier_counts = list(solvedLog_collevtion.aggregate([
        {'$match': {'baekjoon_id': bj}},
        {'$group': {'_id': '$tier', 'count': {'$sum': 1}}},
        {'$sort': {'_id': 1}}
    ]))

    # 간단 랭킹(필요 시 캐시/사전 계산 권장)
    rank_cursor = users_collection.find({}, {'_id':0,'backjun_id':1,'problem_point':1,'review_point':1})
    sorted_users = sorted(rank_cursor, key=lambda u: (u.get('problem_point',0), u.get('review_point',0)), reverse=True)
    rank = next((i+1 for i,u in enumerate(sorted_users) if u.get('backjun_id') == bj), None)

    return jsonify({
        'success': True,
        'data': {
            'profile': user,
            'stats': {
                'total': total,
                'today': today,
                'review_point': review_point,
                'rank': rank,
                'tier_counts': tier_counts
            }
        }
    })

@app.route('/api/backjun/update_usersProfile', methods=["POST"])
def update_usersProfile():

    return


if __name__ == '__main__':  
   app.run('0.0.0.0', port=5001, debug=True)