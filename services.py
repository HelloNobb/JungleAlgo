# services.py
import time
from datetime import datetime, timedelta

import pytz
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

# ---- Mongo 연결 / 핸들 ----
mongo = MongoClient("localhost", 27017)
db = mongo.jungle_algo
users = db.users
solved_log = db.solved_log

# 인덱스(존재 시 무시)
solved_log.create_index([("baekjoon_id", 1), ("problem_id", 1)], unique=True)
solved_log.create_index([("baekjoon_id", 1), ("solved_at", -1)])
solved_log.create_index([("baekjoon_id", 1), ("difficulty", 1)])

UA = {"User-Agent": "Mozilla/5.0 (compatible; JungleAlgo/1.0)"}
KST = pytz.timezone("Asia/Seoul")

# ---- 공통 유틸 ----
def now_kst():
    return datetime.now(KST)

def today_range_kst_utc():
    start_kst = now_kst().replace(hour=0, minute=0, second=0, microsecond=0)
    end_kst = start_kst + timedelta(days=1)
    return start_kst.astimezone(pytz.UTC), end_kst.astimezone(pytz.UTC)

def parse_int_safe(x):
    if x is None: return None
    try: return int(str(x).replace(",", "").strip())
    except Exception: return None

# ---- 백준 프로필 ----
def fetch_baekjoon_profile(baekjoon_id: str):
    r = requests.get(f"https://www.acmicpc.net/user/{baekjoon_id}", headers=UA, timeout=10)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"

    soup = BeautifulSoup(r.text, "html.parser")
    tbody = soup.select_one("#statics > tbody")
    if not tbody:
        return None, "stats table not found"

    result = {}
    for tr in tbody.select("tr"):
        th, td = tr.select_one("th"), tr.select_one("td")
        if th and td:
            result[th.get_text(strip=True)] = td.get_text(strip=True)

    return {
        "rank":   parse_int_safe(result.get("등수")),
        "correct": parse_int_safe(result.get("맞은 문제")),
        "failed":  parse_int_safe(result.get("시도했지만 맞지 못한 문제")),
    }, None

def register_user(baekjoon_id: str):
    # users 컬렉션의 키명은 backjun_id (기존 코드 유지)
    if users.find_one({"backjun_id": baekjoon_id}):
        return False, "이미 등록된 사용자"

    prof, err = fetch_baekjoon_profile(baekjoon_id)
    if err:
        return False, err

    users.insert_one({
        "backjun_id": baekjoon_id,
        "rank": prof["rank"],
        "backjun_correct": prof["correct"] or 0,
        "backjun_failed":  prof["failed"]  or 0,
        "today_goal": 0,
        "created_at": datetime.utcnow(),
    })
    return True, "OK"

def update_user_profile(baekjoon_id: str):
    prof, err = fetch_baekjoon_profile(baekjoon_id)
    if err:
        return False
    users.update_one(
        {"backjun_id": baekjoon_id},
        {"$set": {
            "rank": prof["rank"],
            "backjun_correct": prof["correct"],
            "backjun_failed": prof["failed"],
            "updated_at": datetime.utcnow()
        }}
    )
    return True

# ---- solved.ac 난이도 ----
def get_problem_difficulty(problem_id: int):
    try:
        res = requests.get(
            f"https://solved.ac/api/v3/problem/show?problemId={problem_id}",
            headers=UA, timeout=5
        )
        if res.status_code != 200:
            return None
        level = res.json().get("level", 0)
        if level <= 5:   return "Bronze"
        if level <= 10:  return "Silver"
        if level <= 15:  return "Gold"
        if level <= 20:  return "Platinum"
        if level <= 25:  return "Diamond"
        return "Ruby"
    except Exception:
        return None

# ---- 오늘 제출 파싱/업서트 ----
def parse_status_rows_today(baekjoon_id: str):
    url = f"https://www.acmicpc.net/status?problem_id=&user_id={baekjoon_id}&language_id=-1&result_id=-1"
    resp = requests.get(url, headers=UA, timeout=10)
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("#status-table") or soup.select_one("table")
    if not table:
        return []

    start_utc, end_utc = today_range_kst_utc()
    items = []
    for tr in table.select("tr"):
        link = tr.select_one('a[href^="/problem/"]')
        ts_el = tr.select_one("[data-timestamp]")
        if not link or not ts_el:
            continue

        pid_text = link.get_text(strip=True)
        if not pid_text.isdigit():
            continue
        pid = int(pid_text)

        ts = ts_el.get("data-timestamp")
        if not ts or not str(ts).isdigit():
            continue

        utc_dt = datetime.utcfromtimestamp(int(ts)).replace(tzinfo=pytz.UTC)
        if not (start_utc <= utc_dt < end_utc):
            continue

        items.append({
            "problem_id": pid,
            "solved_at_utc": utc_dt,
            "date_kst": utc_dt.astimezone(KST).strftime("%Y-%m-%d")
        })
    return items

def upsert_today_submissions(baekjoon_id: str, items):
    updated = 0
    for it in items:
        diff = get_problem_difficulty(it["problem_id"])
        # solved_log는 baekjoon_id 필드 사용(기존 유지)
        solved_log.update_one(
            {"baekjoon_id": baekjoon_id, "problem_id": it["problem_id"]},
            {"$setOnInsert": {"title": None},
             "$set": {
                 "date": it["date_kst"],
                 "solved_at": it["solved_at_utc"],
                 "result": "correct",
                 "review": False,
                 "difficulty": diff
             },
             "$inc": {"submission_count": 1}},
            upsert=True
        )
        updated += 1
        time.sleep(0.1)  # 과호출 방지
    return updated

# ---- 대시보드 요약/주간 ----
def dashboard_summary(baekjoon_id: str):
    start_utc, end_utc = today_range_kst_utc()

    total = solved_log.count_documents({"baekjoon_id": baekjoon_id})
    today = solved_log.count_documents({
        "baekjoon_id": baekjoon_id,
        "solved_at": {"$gte": start_utc, "$lt": end_utc}
    })

    agg = list(solved_log.aggregate([
        {"$match": {"baekjoon_id": baekjoon_id}},
        {"$group": {"_id": None, "review_point": {"$sum": "$review_point"}}}
    ]))
    review_point = (agg[0]["review_point"] if agg else 0)

    raw = list(solved_log.aggregate([
        {"$match": {"baekjoon_id": baekjoon_id}},
        {"$group": {"_id": "$difficulty", "count": {"$sum": 1}}}
    ]))
    badges = {r["_id"]: r["count"] for r in raw if r["_id"]}
    for k in ["Ruby","Diamond","Platinum","Gold","Silver","Bronze"]:
        badges.setdefault(k, 0)

    # 간단 티어 규칙(원하면 수정)
    tier = ("Master" if total >= 500 else
            "Diamond" if total >= 300 else
            "Platinum" if total >= 200 else
            "Gold" if total >= 100 else
            "Silver" if total >= 50 else
            "Bronze")

    return {
        "today": today,
        "total": total,
        "review_point": review_point,
        "badges": badges,
        "tier": tier
    }

def weekly_counts_mon_sun(baekjoon_id: str):
    """월~일 7일 카운트 반환 (Chart.js 라벨 Mon..Sun에 맞춤)"""
    now = now_kst()
    # 월요일 0시
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    start_str = start.strftime("%Y-%m-%d")
    end_str = (start + timedelta(days=6)).strftime("%Y-%m-%d")

    rows = list(solved_log.aggregate([
        {"$match": {"baekjoon_id": baekjoon_id, "date": {"$gte": start_str, "$lte": end_str}}},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}}
    ]))
    m = {r["_id"]: r["count"] for r in rows}

    return [int(m.get((start + timedelta(days=i)).strftime("%Y-%m-%d"), 0)) for i in range(7)]
