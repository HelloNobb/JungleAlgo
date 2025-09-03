# 로그인/JWT 관련
from flask import Blueprint, request, jsonify, render_template
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
from app import db, bcrypt  # db, bcrypt 가져오기

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/loginpage')
def loginpage():
    return render_template('login.html')

@auth_bp.route('/signuppage')
def signuppage():
    return render_template('signup.html')

@auth_bp.route("/signuppage/checkid", methods=["POST"])
def checkid():
    id_receive = request.form['userid_give']
    memo = db.memos.find_one({"id": id_receive})
    if memo:
        return jsonify({"result": "fail", "msg": "이미 존재하는 아이디입니다."})
    return jsonify({"result": "success"})

@auth_bp.route("/signuppage/signup", methods=["POST"])
def signup():
    id_receive = request.form['userid_give']
    email_receive = request.form['useremail_give']
    password_receive = request.form['password_give']
    hashed_password = bcrypt.generate_password_hash(password_receive)
    
    memos = {'id': id_receive, 'email': email_receive, 'hashed_password': hashed_password}
    db.memos.insert_one(memos)
    return jsonify({'result': 'success'})

@auth_bp.route("/loginpage/login", methods=["POST"])
def login():
    id_receive = request.form['userid_give']
    password_receive = request.form['password_give']
    memo = db.memos.find_one({"id": id_receive})
    if memo:
        hashed_password = memo.get("hashed_password")
        if bcrypt.check_password_hash(hashed_password, password_receive):
            access_token = create_access_token(identity=id_receive, expires_delta=timedelta(minutes=30))
            return jsonify({"result": "success", "access_token": access_token})
        return jsonify({"result": "fail", "msg": "비밀번호가 일치하지 않습니다."})
    else:
        return jsonify({"result": "fail", "msg": "존재하지 않는 사용자입니다."})

@auth_bp.route('/useronly', methods=["GET"])
@jwt_required()
def user_only_api():
    cur_user = get_jwt_identity()
    return jsonify({"username": cur_user, "msg": "API 접근 성공!"})
