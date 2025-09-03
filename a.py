from flask import Flask, render_template, jsonify, request, redirect, url_forz
from flask_jwt_extended import *
from pymongo import MongoClient  # pymongo를 임포트 하기(패키지 인스톨 먼저 해야겠죠?)
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt
client = MongoClient('localhost', 27017)
db = client.dbjungle  # 'dbjungle'라는 이름의 db를 만들거나 사용합니다.
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
def jwt_required(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            # 토큰이 없으면 로그인 페이지로 리다이렉트
            return redirect(url_for('login_page'))
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            # 토큰이 만료되면 로그인 페이지로 리다이렉트
            return redirect(url_for('login_page'))
        except jwt.InvalidTokenError:
            # 토큰이 유효하지 않으면 로그인 페이지로 리다이렉트
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__ # Wrapper 함수의 이름 설정
    return wrapper
@app.route('/')
def home():
    return render_template('login.html')
@app.route('/loginpage')
def loginpage():
    return render_template('login.html')
@app.route('/signuppage')
def signuppage():
    return render_template('signup.html')
@app.route('/reviewpage')
def reviewpage():
    return render_template('reviews.html')
@app.route("/signuppage/checkid", methods=["POST"])
def checkid():
    id_receive = request.form['userid_give']
    memo=db.memos.find_one({"id": id_receive})
    if(memo):
        return jsonify({"result": "fail", "msg": "이미 존재하는 아이디입니다."})
    return jsonify({"result": "success"})
@app.route("/signuppage/signup", methods=["POST"])
def signup():
    # 1. 클라이언트로부터 데이터를 받기
    id_receive = request.form['userid_give']
    email_receive = request.form['useremail_give']
    password_receive = request.form['password_give']
    hashed_password = bcrypt.generate_password_hash(password_receive)
    # 보안을 위해 password_receive를 사용 후 삭제합니다.
    del password_receive
    memos = {'id':id_receive, 'email': email_receive, 'hashed_password': hashed_password}
    db.memos.insert_one(memos)
    return jsonify({'result': 'success'})
@app.route("/loginpage/login", methods=["POST"])
def login():
    id_receive = request.form['userid_give']
    password_receive = request.form['password_give']
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
@app.route('/api/reviews/create', methods=['POST'])
@jwt_required()
def create_review():
    try:
        now = datetime.now()
        review_text=request.form['review_text']
        problem_id=request.form['problem_id']
        backjun_id = get_jwt_identity()
        review_date=now.strftime('%Y-%m-%d-%H:%M:%S')
        star = request.form['star']
        difficulty = get_problem_difficulty(problem_id)
        # MongoDB에 리뷰 데이터 저장
        db.solved_log.insert_one({
            'review_text': review_text,
            'problem_id': problem_id,
            'backjun_id': backjun_id,
            'review_date': review_date,
            'star': star,
            'difficulty': difficulty
        })
        return jsonify({'result': 'success'})
    except Exception as e:
            print(f"An error occurred: {e}")
            return jsonify({"result": "error", "message": "Internal Server Error"}), 500
from flask import request
@app.route('/api/reviews/delete', methods=['DELETE'])
@jwt_required()
def delete_review():
    problem_id = request.form.get("problem_id")
    if not problem_id:
        return jsonify({"result": "error", "message": "problem_id가 누락되었습니다."}), 400
    backjun_id = get_jwt_identity()
    result = db.solved_log.delete_one({'problem_id': problem_id, 'backjun_id': backjun_id})
    if result.deleted_count > 0:
        return jsonify({'result': 'success', 'message': '리뷰가 성공적으로 삭제되었습니다.'})
    else:
        return jsonify({'result': 'fail', 'message': '해당 리뷰를 찾을 수 없거나 삭제 권한이 없습니다.'}), 403
@app.route('/api/reviews/update', methods=['POST'])
@jwt_required()
def update_review():
    now = datetime.now()
    problem_id = request.form['problem_id']
    edited_text = request.form['edited_text']
    edited_star = request.form['edited_star']
    backjun_id = get_jwt_identity()
    review_date=now.strftime('%Y-%m-%d-%H:%M:%S')
    db.solved_log.update_one({'problem_id': problem_id, 'backjun_id': backjun_id}, {
        '$set': {
            'review_text': edited_text,
            'star': edited_star,
            'review_date': review_date
        }
    })
    return jsonify({'result': 'success'})
@app.route('/api/reviews/show', methods=['GET'])
@jwt_required()
def show_reviews():
    result = list(db.solved_log.find({}, {'_id': False}).sort([("review_date", -1)]))
    return jsonify({'result': 'success', 'reviews': result, 'current_user_id': get_jwt_identity()})
#풀고 리뷰 안한 문제 가져오기
@app.route('/api/reviews/nonreviewed', methods=['GET'])
@jwt_required()
def nonReviewedProblems():
    current_user_id = get_jwt_identity()
    reviewed_problems_cursor = db.solved_logs.find(
        {
            'backjun_id': current_user_id,
            'review': 0
        },
        {'problem_id': 1} # 문제 번호 필드만 가져와 최적화합니다.
    )
    non_reviewed = [problem['problem_id'] for problem in reviewed_problems_cursor]
    return jsonify({'result': 'success', 'non_reviewed_problems': non_reviewed})
if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)