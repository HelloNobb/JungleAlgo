#app.py
from flask import Flask, app, render_template, request, jsonify
from flask_jwt_extended import *
from pymongo import MongoClient
from datetime import timedelta
from flask_bcrypt import Bcrypt

# pip install flask-bcrypt
# pip install flask-jwt-extended

app = Flask(__name__)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
client = MongoClient('localhost', 27017)
db = client.dbjungle  # 'dbjungle'라는 이름의 db를 만들거나 사용합니다.

app.config.update(
    DEBUG=True,
    # JWT에만 사용될 시크릿 키
    JWT_SECRET_KEY="myAlgorithmJWT",
    # bcrypt의 난이도 설정
    BCRYPT_LEVEL=10
)

@app.route('/useronly', methods=["GET"])
@jwt_required()
def user_only_api():
    cur_user = get_jwt_identity()
    return jsonify({"username": cur_user, "msg": "API 접근 성공!"})

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/loginpage')
def loginpage():
    return render_template('login.html')

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

@app.route("/loginpage/login", methods=["POST"])
def login():
    #data: {userid_give: userid, password_give: password}, // data라는 이름으로 userid와 password를 줄게
    id_receive = request.form['userid_give']  # 클라이언트로부터 id를 받는 부분
    password_receive = request.form['password_give']  # 클라이언트로부터 비밀번호를 받는 부분
    memo = db.memos.find_one({"id": id_receive})
    if memo:
        hashed_password = memo.get("hashed_password")
        if bcrypt.check_password_hash(hashed_password, password_receive):
            # 아이디와 비밀번호가 맞다면 토큰을 생성합니다.
            access_token = create_access_token(identity=id_receive, expires_delta=timedelta(minutes=30))
            return jsonify({"result": "success", "access_token": access_token})
        return jsonify({"result": "fail", "msg": "비밀번호가 일치하지 않습니다."})
    else:
        return jsonify({"result": "fail", "msg": "존재하지 않는 사용자입니다."})


if __name__ == '__main__':
	app.run(host = '0.0.0.0',
					port = 5000, 
					debug = True)