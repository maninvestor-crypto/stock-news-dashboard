import os
import json
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv, find_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo
from news_fetcher import get_news_links, extract_article_text
from ai_summarizer import summarize_text

load_dotenv(find_dotenv(), override=True)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin1234")

# ─── 파일 경로 ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
KEYWORDS_FILE  = os.path.join(BASE_DIR, "keywords.json")
BOOKMARKS_FILE = os.path.join(BASE_DIR, "bookmarks.json")
DEFAULT_KEYWORDS = ["삼성전자", "SK하이닉스", "AI 인프라", "바이오"]

# 중요 키워드 (제목에 포함 시 🚨 강조)
ALERT_KEYWORDS = [
    "급락", "급등", "폭락", "파산", "상장폐지", "영업정지",
    "FDA 승인", "FDA", "임상", "합병", "인수", "공매도",
    "어닝쇼크", "어닝서프라이즈", "반등", "역대", "최저", "최고",
    "긴급", "위기", "제재", "압수수색", "구속",
]

# ─── 파일 I/O 유틸 ───────────────────────────────────────────────────────────
def load_keywords():
    try:
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and data:
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return DEFAULT_KEYWORDS.copy()

def save_keywords(keywords):
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)

def load_bookmarks():
    try:
        with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_bookmarks(bookmarks):
    with open(BOOKMARKS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, ensure_ascii=False, indent=2)

# ─── 유틸 함수 ───────────────────────────────────────────────────────────────
def get_score_badge(score):
    """점수에 따른 배지 텍스트와 색상 반환"""
    if score >= 9:
        return "🚨 매우 높음", "#ff4444"
    elif score >= 7:
        return "🔴 높음", "#ff8c00"
    elif score >= 4:
        return "🟡 보통", "#ffd700"
    elif score >= 1:
        return "🟢 낮음", "#4caf50"
    return "⚪ -", "#888888"

def check_alert_keywords(title):
    """제목에 중요 키워드 포함 여부 확인"""
    return [kw for kw in ALERT_KEYWORDS if kw in title]

# ─── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="실시간 증권 뉴스 요약",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.summary-box {
    background-color: #1e2130;
    border-left: 4px solid #4f8ef7;
    border-radius: 6px;
    padding: 14px 18px;
    margin: 8px 0 16px 0;
    line-height: 1.8;
}
.summary-box-alert {
    background-color: #2a1a1a;
    border-left: 4px solid #ff4444;
    border-radius: 6px;
    padding: 14px 18px;
    margin: 8px 0 16px 0;
    line-height: 1.8;
}
.keyword-tag {
    display: inline-block;
    background: #2c3354;
    color: #a8c0ff;
    border-radius: 20px;
    padding: 3px 12px;
    margin: 3px 3px;
    font-size: 0.85em;
    font-weight: 500;
}
.alert-tag {
    display: inline-block;
    background: #5a1a1a;
    color: #ff8888;
    border-radius: 20px;
    padding: 2px 10px;
    margin: 2px 2px;
    font-size: 0.78em;
    font-weight: 700;
}
.score-badge {
    display: inline-block;
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 0.85em;
    font-weight: 700;
    margin-left: 8px;
}
.refresh-info {
    font-size: 0.8em;
    color: #888;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)

# ─── 세션 상태 초기화 ────────────────────────────────────────────────────────
if "keywords" not in st.session_state:
    st.session_state.keywords = load_keywords()

if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = load_bookmarks()

if "auto_refresh_min" not in st.session_state:
    st.session_state.auto_refresh_min = 30

if "num_news" not in st.session_state:
    st.session_state.num_news = 2

if "seen_links" not in st.session_state:
    st.session_state.seen_links = set()

if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

if "show_bookmarks" not in st.session_state:
    st.session_state.show_bookmarks = False

# ─── 사이드바 ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 설정")
    st.markdown("---")

    # 뷰 전환 버튼
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📰 뉴스", use_container_width=True,
                     type="primary" if not st.session_state.show_bookmarks else "secondary"):
            st.session_state.show_bookmarks = False
            st.rerun()
    with col_b:
        bm_count = len(st.session_state.bookmarks)
        if st.button(f"📌 북마크 ({bm_count})", use_container_width=True,
                     type="primary" if st.session_state.show_bookmarks else "secondary"):
            st.session_state.show_bookmarks = True
            st.rerun()

    st.markdown("---")

    # 1) 키워드 관리
    st.subheader("🔍 키워드 관리")
    st.markdown(" **등록된 키워드:**")
    for kw in list(st.session_state.keywords):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f'<span class="keyword-tag">{kw}</span>', unsafe_allow_html=True)
        with col2:
            if st.session_state.is_admin:
                if st.button("✕", key=f"del_{kw}", help=f"'{kw}' 삭제"):
                    st.session_state.keywords.remove(kw)
                    save_keywords(st.session_state.keywords)
                    st.rerun()
            else:
                st.markdown("🔒", unsafe_allow_html=True)

    st.markdown("---")

    # 관리자 인증
    if not st.session_state.is_admin:
        st.markdown("🔐 **키워드 편집 (관리자 전용)**")
        pw_input = st.text_input("비밀번호 입력", type="password", key="pw_input")
        if st.button("키워드 편집 토글", use_container_width=True):
            if pw_input == DASHBOARD_PASSWORD:
                st.session_state.is_admin = True
                st.success("✅ 관리자 모드 활성화")
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀립니다.")
    else:
        st.success("✅ 관리자 모드")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.is_admin = False
            st.rerun()
        new_keyword = st.text_input("키워드 추가", placeholder="예: 현대차, 2차전지…", key="new_kw_input")
        if st.button("➕ 추가", use_container_width=True):
            kw = new_keyword.strip()
            if kw and kw not in st.session_state.keywords:
                st.session_state.keywords.append(kw)
                save_keywords(st.session_state.keywords)
                st.rerun()
            elif not kw:
                st.warning("키워드를 입력해 주세요.")
            else:
                st.warning("이미 등록된 키워드입니다.")

    st.markdown("---")

    # 2) 뉴스 개수
    st.subheader("📰 뉴스 개수")
    st.session_state.num_news = st.slider(
        "키워드당 뉴스 수", min_value=1, max_value=5,
        value=st.session_state.num_news
    )

    st.markdown("---")

    # 3) 자동 새로고침
    st.subheader("🔄 자동 새로고침")
    refresh_options = {"사용 안함": 0, "10분": 10, "30분": 30, "1시간": 60}
    selected_refresh = st.selectbox(
        "새로고침 주기",
        options=list(refresh_options.keys()),
        index=list(refresh_options.values()).index(st.session_state.auto_refresh_min)
        if st.session_state.auto_refresh_min in refresh_options.values() else 0
    )
    st.session_state.auto_refresh_min = refresh_options[selected_refresh]
    if st.session_state.auto_refresh_min > 0:
        st.success(f"✅ {selected_refresh}마다 자동 갱신 중")
    else:
        st.info("자동 새로고침 꺼짐")

    st.markdown("---")

    # 4) 읽은 뉴스 관리
    st.subheader("🗑 읽은 뉴스 관리")
    seen_count = len(st.session_state.seen_links)
    if seen_count > 0:
        st.info(f"현재 {seen_count}개의 뉴스가 숨김 처리되어 있습니다.")
        if st.button("🔄 읽은 뉴스 초기화", use_container_width=True):
            st.session_state.seen_links = set()
            st.rerun()
    else:
        st.caption("숨김 처리된 뉴스가 없습니다.")

    st.markdown("---")

    # 5) 수동 새로고침
    if st.button("⚡ 지금 새로고침", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# ─── 자동 새로고침 ───────────────────────────────────────────────────────────
if st.session_state.auto_refresh_min > 0:
    interval_ms = st.session_state.auto_refresh_min * 60 * 1000
    st_autorefresh(interval=interval_ms, key="auto_refresh")

# ─── 헤더 ────────────────────────────────────────────────────────────────────
st.title("📈 실시간 증권 뉴스 요약 대시보드")
st.markdown("관심 키워드의 최신 뉴스를 가져와 **Gemini AI**가 3줄로 요약합니다.")
kst = ZoneInfo("Asia/Seoul")
now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S KST")
st.markdown(f'<p class="refresh-info">🕐 마지막 갱신: {now_str}</p>', unsafe_allow_html=True)
st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# 📌 북마크 뷰
# ════════════════════════════════════════════════════════════════════════════
if st.session_state.show_bookmarks:
    st.subheader("📌 북마크한 뉴스")
    bookmarks = st.session_state.bookmarks

    if not bookmarks:
        st.info("아직 북마크한 뉴스가 없습니다. 뉴스 카드의 '📌 북마크' 버튼을 눌러 저장해 보세요.")
    else:
        for i, bm in enumerate(bookmarks):
            score = bm.get("score", 0)
            badge_text, badge_color = get_score_badge(score)
            alerts = check_alert_keywords(bm.get("title", ""))
            alert_str = " ".join([f'<span class="alert-tag">🚨 {kw}</span>' for kw in alerts])

            header = f"📰 {bm['title']}"
            with st.expander(header, expanded=False):
                # 상단 메타
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"🗓 {bm.get('published','날짜 미상')} | [원문 기사 보러가기]({bm['link']})")
                    if alert_str:
                        st.markdown(alert_str, unsafe_allow_html=True)
                with col2:
                    st.markdown(
                        f'<div style="text-align:right; color:{badge_color}; font-weight:700; font-size:1em;">'
                        f'중요도 {score}/10<br>{badge_text}</div>',
                        unsafe_allow_html=True
                    )

                box_class = "summary-box-alert" if alerts else "summary-box"
                st.markdown(
                    f'<div class="{box_class}">{bm.get("summary","요약 없음")}</div>',
                    unsafe_allow_html=True,
                )

                if st.button("🗑 북마크 해제", key=f"unbm_{i}"):
                    st.session_state.bookmarks.pop(i)
                    save_bookmarks(st.session_state.bookmarks)
                    st.rerun()
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# 📰 뉴스 뷰
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.keywords:
    st.warning("왼쪽 사이드바에서 키워드를 추가해 주세요.")
    st.stop()

for keyword in st.session_state.keywords:
    st.markdown(f"### 🔍 `{keyword}`")

    with st.spinner(f"'{keyword}' 뉴스 수집 중..."):
        articles = get_news_links(keyword, max_items=st.session_state.num_news)

    if not articles:
        st.warning(f"'{keyword}' 관련 최신 뉴스를 찾을 수 없습니다.")
        continue

    new_articles = [a for a in articles if a["link"] not in st.session_state.seen_links]
    skipped = len(articles) - len(new_articles)
    if skipped > 0:
        st.caption(f"ℹ️ 이미 제공된 뉴스 {skipped}건은 제외되었습니다.")

    if not new_articles:
        st.info(f"'{keyword}' 의 새로운 뉴스가 없습니다. 사이드바에서 읽은 뉴스를 초기화하거나 나중에 다시 확인해 주세요.")
        st.markdown("---")
        continue

    for article in new_articles:
        title     = article["title"]
        link      = article["link"]
        published = article.get("published", "날짜 알 수 없음")

        # 이미 본 뉴스로 등록
        st.session_state.seen_links.add(link)

        # 중요 키워드 감지
        alerts = check_alert_keywords(title)
        alert_str = " ".join([f'<span class="alert-tag">🚨 {kw}</span>' for kw in alerts])
        expander_title = f"🚨 {title}" if alerts else f"📰 {title}"

        with st.expander(expander_title, expanded=True):

            with st.spinner("AI 요약 및 중요도 분석 중..."):
                text_content = extract_article_text(link)
                result = summarize_text(text_content, fallback_title=title)

            summary = result.get("summary", "요약 실패")
            score   = result.get("score", 0)
            badge_text, badge_color = get_score_badge(score)

            # 상단: 날짜 | 링크 | 중요도
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"🗓 게시일: {published} | [원문 기사 보러가기]({link})")
                if alert_str:
                    st.markdown(alert_str, unsafe_allow_html=True)
            with col2:
                st.markdown(
                    f'<div style="text-align:right; color:{badge_color}; font-weight:700; font-size:1em;">'
                    f'중요도 {score}/10<br>{badge_text}</div>',
                    unsafe_allow_html=True,
                )

            # 요약 박스 (알림 키워드 있으면 붉은 테두리)
            box_class = "summary-box-alert" if alerts else "summary-box"
            st.markdown("**🤖 AI 3줄 요약:**")
            st.markdown(f'<div class="{box_class}">{summary}</div>', unsafe_allow_html=True)

            if not text_content:
                st.warning("⚠️ 원문 접근이 차단되어 제목 기반으로 AI가 추론한 요약입니다.")

            # 북마크 버튼
            bm_links = [b["link"] for b in st.session_state.bookmarks]
            if link in bm_links:
                st.success("📌 북마크됨")
            else:
                if st.button("📌 북마크", key=f"bm_{link}"):
                    new_bm = {
                        "title": title,
                        "link": link,
                        "published": published,
                        "summary": summary,
                        "score": score,
                        "saved_at": datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"),
                    }
                    st.session_state.bookmarks.append(new_bm)
                    save_bookmarks(st.session_state.bookmarks)
                    st.success("📌 북마크에 저장되었습니다!")
                    st.rerun()

    st.markdown("---")
