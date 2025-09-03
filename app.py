# from turtle import back
import requests
import json
import re

from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient
app = Flask(__name__)

client = MongoClient('localhost', 27017)
db = client.jungle_algo

users_collection = db.users


@app.route('/')
def home():
   return render_template('index.html')



@app.route('/api/register', methods=["POST"])
def register():
    # data = request.get_json()
    # backjun_id = data.get('backjun_id')
    headers = {'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}
    response = requests.get(f'https://www.acmicpc.net/user/0224seo', headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    stats_table = soup.select_one('#statics > tbody')
   # 테이블 형식의 데이터를 가공해서 객체 형태로 변환
    result = {}

    if not stats_table:
        return jsonify({
            'success' : False,
            'message' : '사용자 정보를 찾을 수 없습니다.'
        }), 404
    rows = stats_table.select('tbody tr')

    for row in rows:
           th = row.select_one('th')
           td = row.select_one('td')
           
           if th and td:
               key = th.get_text(strip=True)
               value = td.get_text(strip=True)
               result[key] = value

    
    backjun_rank = result.get('등수')
    # backjun_solved_count = result.get('맞은 문제')

    user_data = {
        'backjun_id' : '0224seo',
        'rank': int(backjun_rank)
    }

    users_collection.insert_one(user_data)

    # # backjun_id = result.key
    return app.response_class(
           response=json.dumps({
               'success': True,
               'data': result,
           }, ensure_ascii=False),
           mimetype='application/json; charset=utf-8'
       )



if __name__ == '__main__':  
   app.run('0.0.0.0', port=5001, debug=True)