#!/usr/bin/env python3
"""
서울과학기술대학교 대학공지사항(최근 1년) Q&A 프로그램
- 게시판 목록을 크롤링 -> 최근 1년 게시물만 필터 -> 본문 인덱싱
- 질문과 매칭되는 게시물을 찾아 요약 응답. 근거 없으면 "모른다"고 응답.

requirements: requests, beautifulsoup4
usage:
    python seoultech_notice_qa.py --build      # 게시물 수집/캐시 생성
    python seoultech_notice_qa.py --ask "장학금 신청 언제까지야?"
    python seoultech_notice_qa.py              # 대화형 모드
"""
import re, os, sys, json, argparse, datetime as dt
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("pip install requests beautifulsoup4 필요")

BASE = "https://www.seoultech.ac.kr"
LIST_URL = BASE + "/service/info/notice"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notice_cache.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NoticeQA/1.0)"}
ONE_YEAR = dt.timedelta(days=365)

# ---------------------------------------------------------------- 수집
def fetch(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text

def parse_date(s):
    s = s.strip()
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    return None

def parse_list_page(html):
    """게시판 목록 한 페이지에서 (제목, 링크, 날짜) 추출."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # 테이블형 게시판 표준 파싱 (구조 변경 시 셀렉터만 조정)
    for tr in soup.select("table tbody tr"):
        a = tr.find("a", href=True)
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        href = urljoin(BASE, a["href"])
        date = None
        for td in tr.find_all("td"):
            d = parse_date(td.get_text())
            if d:
                date = d
        if title:
            rows.append({"title": title, "url": href, "date": date.isoformat() if date else None})
    return rows

def fetch_body(url):
    try:
        soup = BeautifulSoup(fetch(url), "html.parser")
    except Exception:
        return ""
    node = (soup.select_one(".bbs_view, .board_view, #hcms_content, .view_con")
            or soup.find("article") or soup.body)
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True))[:4000] if node else ""

def build(max_pages=30):
    cutoff = dt.date.today() - ONE_YEAR
    posts, stop = [], False
    for page in range(1, max_pages + 1):
        try:
            html = fetch(LIST_URL, params={"pageIndex": page})
        except Exception as e:
            print(f"[page {page}] 요청 실패: {e}", file=sys.stderr)
            break
        rows = parse_list_page(html)
        if not rows:
            break
        for r in rows:
            d = parse_date(r["date"]) if r["date"] else None
            if d and d < cutoff:
                stop = True
                continue
            r["body"] = fetch_body(r["url"])
            posts.append(r)
        print(f"[page {page}] 누적 {len(posts)}건")
        if stop:
            break
    json.dump({"built": dt.date.today().isoformat(), "posts": posts},
              open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"완료: {len(posts)}건 저장 -> {CACHE}")
    return posts

def load():
    if not os.path.exists(CACHE):
        return None
    data = json.load(open(CACHE, encoding="utf-8"))
    # 캐시가 24시간 이상 오래되면 경고
    if data.get("built") != dt.date.today().isoformat():
        print("(안내) 캐시가 오늘자가 아닙니다. --build 권장", file=sys.stderr)
    return data["posts"]

# ---------------------------------------------------------------- 검색/응답
STOP = set("은 는 이 가 을 를 에 의 도 으로 와 과 어떻게 무엇 뭐 언제 어디 누가 왜 알려줘 해줘 인가요 인가 야 까".split())

def tokens(s):
    return [w for w in re.findall(r"[가-힣A-Za-z0-9]+", s.lower()) if w not in STOP and len(w) > 1]

def search(question, posts, topk=3):
    q = tokens(question)
    if not q:
        return []
    scored = []
    for p in posts:
        text = (p["title"] + " " + p.get("body", "")).lower()
        title = p["title"].lower()
        score = sum(text.count(w) for w in q) + sum(3 for w in q if w in title)
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:topk]

def answer(question, posts):
    hits = search(question, posts)
    if not hits:
        return "해당 내용은 최근 1년 공지사항에서 찾을 수 없어 모르겠습니다."
    out = ["다음 공지사항에서 관련 내용을 찾았습니다:\n"]
    for i, (score, p) in enumerate(hits, 1):
        snippet = p.get("body", "")[:200]
        out.append(f"{i}. {p['title']} ({p.get('date','날짜미상')})\n   {snippet}...\n   링크: {p['url']}")
    return "\n".join(out)

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="게시물 수집/캐시 생성")
    ap.add_argument("--ask", help="질문")
    ap.add_argument("--pages", type=int, default=30)
    args = ap.parse_args()

    if args.build:
        build(args.pages); return
    posts = load()
    if posts is None:
        print("캐시 없음 -> 수집 시작"); posts = build(args.pages)
    if args.ask:
        print(answer(args.ask, posts)); return
    print("대화형 모드 (종료: quit)")
    while True:
        try:
            q = input("질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q in ("quit", "exit", ""):
            break
        print(answer(q, posts), "\n")

if __name__ == "__main__":
    main()
