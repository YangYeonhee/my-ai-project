#!/usr/bin/env python3
"""
서울과학기술대학교 공지사항 Q&A - 웹 서비스 (Flask)
- 기존 app.py 의 크롤링/검색 로직을 그대로 재사용하고 웹 UI 와 JSON API 를 얹었다.
- 로컬:  python server.py        -> http://127.0.0.1:5000
- 배포:  gunicorn server:app     (Render Procfile 참고)
"""
import os
import datetime as dt
from flask import Flask, render_template, request, jsonify

# 기존 CLI 프로그램의 함수 재사용 (app.py 의 main() 은 __main__ 가드라 import 시 실행 안 됨)
import app as qa

application = Flask(__name__)
app = application  # gunicorn server:app 호환

# 메모리 캐시 (요청마다 디스크 재로딩 방지)
_POSTS = None


def get_posts(force_reload=False):
    """캐시된 게시물 목록을 반환. 없으면 None."""
    global _POSTS
    if _POSTS is None or force_reload:
        _POSTS = qa.load()
    return _POSTS


def search_structured(question, posts, topk=3):
    """app.search() 결과를 웹/JSON 친화적인 dict 리스트로 변환."""
    hits = qa.search(question, posts, topk=topk)
    results = []
    for score, p in hits:
        body = p.get("body", "") or ""
        results.append({
            "title": p["title"],
            "date": p.get("date") or "날짜미상",
            "url": p["url"],
            "snippet": body[:240] + ("..." if len(body) > 240 else ""),
            "score": score,
        })
    return results


# ---------------------------------------------------------------- 라우트
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """캐시 상태(수집일/건수)를 반환."""
    posts = get_posts()
    built = None
    if os.path.exists(qa.CACHE):
        import json
        try:
            built = json.load(open(qa.CACHE, encoding="utf-8")).get("built")
        except Exception:
            built = None
    return jsonify({
        "ready": posts is not None,
        "count": len(posts) if posts else 0,
        "built": built,
        "today": dt.date.today().isoformat(),
    })


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """질문 -> 관련 공지 검색 결과(JSON)."""
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "질문을 입력하세요."}), 400

    posts = get_posts()
    if posts is None:
        return jsonify({
            "ready": False,
            "message": "아직 수집된 공지 데이터가 없습니다. 먼저 '데이터 수집'을 실행하세요.",
            "hits": [],
        })

    hits = search_structured(question, posts, topk=3)
    if not hits:
        return jsonify({
            "ready": True,
            "message": "해당 내용은 최근 1년 공지사항에서 찾을 수 없어 모르겠습니다.",
            "hits": [],
        })
    return jsonify({
        "ready": True,
        "message": "다음 공지사항에서 관련 내용을 찾았습니다.",
        "hits": hits,
    })


@app.route("/api/build", methods=["POST"])
def api_build():
    """공지 게시판을 크롤링해 캐시를 새로 만든다. (시간이 걸릴 수 있음)"""
    data = request.get_json(silent=True) or {}
    try:
        pages = int(data.get("pages", 5))
    except (TypeError, ValueError):
        pages = 5
    pages = max(1, min(pages, 30))  # 안전 범위
    try:
        posts = qa.build(max_pages=pages)
    except Exception as e:
        return jsonify({"ok": False, "error": f"수집 실패: {e}"}), 500
    get_posts(force_reload=True)
    return jsonify({"ok": True, "count": len(posts), "built": dt.date.today().isoformat()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
