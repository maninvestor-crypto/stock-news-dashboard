import streamlit as st
from streamlit_autorefresh import st_autorefresh
from news_fetcher import get_news_links, extract_article_text
from ai_summarizer import summarize_text

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
/* 구글 폰트 */
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
.refresh-info {
    font-size: 0.8em;
    color: #888;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)

# ─── 세션 상태 초기화 ────────────────────────────────────────────────────────
if "keywords" not in st.session_state:
    st.session_state.keywords = ["삼성전자", "SK하이닉스", "AI 인프라", "바이오"]

if "auto_refresh_min" not in st.session_state:
    st.session_state.auto_refresh_min = 30

if "num_news" not in st.session_state:
    st.session_state.num_news = 2

# ─── 사이드바 ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 설정")

    st.markdown("---")

    # 1) 키워드 관리
    st.subheader("🔍 키워드 관리")
    new_keyword = st.text_input("키워드 추가", placeholder="예: 현대차, 2차전지…", key="new_kw_input")
    if st.button("➕ 추가", use_container_width=True):
        kw = new_keyword.strip()
        if kw and kw not in st.session_state.keywords:
            st.session_state.keywords.append(kw)
            st.rerun()
        elif not kw:
            st.warning("키워드를 입력해 주세요.")
        else:
            st.warning("이미 등록된 키워드입니다.")

    # 현재 등록된 키워드 목록 + 삭제 버튼
    st.markdown("**등록된 키워드:**")
    for kw in list(st.session_state.keywords):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f'<span class="keyword-tag">{kw}</span>', unsafe_allow_html=True)
        with col2:
            if st.button("✕", key=f"del_{kw}", help=f"'{kw}' 삭제"):
                st.session_state.keywords.remove(kw)
                st.rerun()

    st.markdown("---")

    # 2) 뉴스 개수 설정
    st.subheader("📰 뉴스 개수")
    st.session_state.num_news = st.slider(
        "키워드당 뉴스 수", min_value=1, max_value=5,
        value=st.session_state.num_news
    )

    st.markdown("---")

    # 3) 자동 새로고침 설정
    st.subheader("🔄 자동 새로고침")
    refresh_options = {
        "사용 안함": 0,
        "10분": 10,
        "30분": 30,
        "1시간": 60,
    }
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

    # 4) 수동 새로고침 버튼
    if st.button("⚡ 지금 새로고침", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# ─── 자동 새로고침 실행 ───────────────────────────────────────────────────────
if st.session_state.auto_refresh_min > 0:
    interval_ms = st.session_state.auto_refresh_min * 60 * 1000
    count = st_autorefresh(interval=interval_ms, key="auto_refresh")

# ─── 메인 대시보드 ────────────────────────────────────────────────────────────
st.title("📈 실시간 증권 뉴스 요약 대시보드")
st.markdown("관심 키워드의 최신 뉴스를 가져와 **Gemini AI**가 3줄로 요약합니다.")

if not st.session_state.keywords:
    st.warning("왼쪽 사이드바에서 키워드를 추가해 주세요.")
    st.stop()

# 새로고침 시각 표시
from datetime import datetime
from zoneinfo import ZoneInfo

kst = ZoneInfo("Asia/Seoul")
now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S KST")
st.markdown(f'<p class="refresh-info">🕐 마지막 갱신: {now_str}</p>', unsafe_allow_html=True)

st.markdown("---")

# ─── 키워드별 뉴스 출력 ──────────────────────────────────────────────────────
for keyword in st.session_state.keywords:
    st.markdown(f"### 🔍 `{keyword}`")

    with st.spinner(f"'{keyword}' 뉴스 수집 및 AI 요약 중..."):
        articles = get_news_links(keyword, max_items=st.session_state.num_news)

    if not articles:
        st.warning(f"'{keyword}' 관련 최신 뉴스를 찾을 수 없습니다.")
        continue

    for article in articles:
        title = article["title"]
        link = article["link"]
        published = article.get("published", "날짜 알 수 없음")

        with st.expander(f"📰 {title}", expanded=True):
            st.caption(f"🗓 게시일: {published} | [원문 기사 보러가기]({link})")

            with st.spinner("AI 요약 생성 중..."):
                text_content = extract_article_text(link)
                summary = summarize_text(text_content, fallback_title=title)

            st.markdown("**🤖 AI 3줄 요약:**")
            st.markdown(
                f'<div class="summary-box">{summary}</div>',
                unsafe_allow_html=True,
            )

            if not text_content:
                st.warning("⚠️ 원문 접근이 차단되어 제목 기반으로 AI가 추론한 요약입니다.")

    st.markdown("---")
