import os
from google import genai
from dotenv import load_dotenv, find_dotenv

# .env 파일을 안전하게 로드
load_dotenv(find_dotenv(), override=True)

# ─── API 키 목록 수집 ────────────────────────────────────────────────────────
def _collect_api_keys():
    keys = []
    k = os.getenv("GEMINI_API_KEY", "").strip()
    if k:
        keys.append(k)
    for i in range(1, 11):
        k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    seen = set()
    unique = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique

API_KEYS = _collect_api_keys()

# 모델 우선순위 목록 (gemini-2.5-flash-lite 최우선)
CANDIDATE_MODELS = [
    "gemini-2.5-flash-lite",   # 최우선
    "gemini-2.5-flash",        # 폴백
]

def _build_prompt(text, fallback_title):
    """요약 + 중요도 점수를 함께 요청하는 프롬프트 생성"""
    base_instruction = """응답은 반드시 아래 형식 그대로 출력하세요. 다른 말은 일절 하지 마세요.

점수: [1~10 사이 정수]
요약:
- [핵심 이슈 1]
- [핵심 이슈 2]
- [핵심 이슈 3]

점수 기준:
1~3: 일반적인 뉴스, 시장 영향 미미
4~6: 주목할 만한 이슈, 단기 영향 가능
7~8: 중요한 이슈, 해당 종목/섹터 주가 영향 예상
9~10: 매우 중요, 시장 전반 또는 업종 판도 변화 가능"""

    if not text and fallback_title:
        return f"""{base_instruction}

아래는 뉴스 기사 제목입니다. 본문 접근이 차단되어 제목만으로 분석합니다.
기사 제목: {fallback_title}"""
    elif text:
        return f"""{base_instruction}

아래는 증권 관련 뉴스 기사 본문입니다.
기사 본문:
{text[:3000]}"""
    return None

def _parse_response(response_text):
    """AI 응답에서 점수와 요약을 파싱합니다."""
    score = 5  # 기본값
    summary_lines = []

    lines = response_text.strip().split("\n")
    in_summary = False

    for line in lines:
        line = line.strip()
        if line.startswith("점수:"):
            try:
                score = int(line.replace("점수:", "").strip())
                score = max(1, min(10, score))  # 1~10 범위 보정
            except ValueError:
                score = 5
        elif line.startswith("요약:"):
            in_summary = True
        elif in_summary and line.startswith("-"):
            summary_lines.append(line)

    summary = "\n".join(summary_lines) if summary_lines else response_text
    return {"summary": summary, "score": score}

def summarize_text(text, fallback_title=""):
    """기사 본문을 입력받아 3줄 요약 + 중요도 점수(1~10)를 반환합니다.
    반환값: {"summary": str, "score": int}
    """
    if not API_KEYS:
        return {
            "summary": "API 키가 설정되지 않아 요약 기능을 사용할 수 없습니다. `.env` 파일을 확인해 주세요.",
            "score": 0
        }

    prompt = _build_prompt(text, fallback_title)
    if prompt is None:
        return {"summary": "기사 본문과 제목을 모두 가져올 수 없습니다.", "score": 0}

    last_error = None

    for api_key in API_KEYS:
        client = genai.Client(api_key=api_key)
        for model_name in CANDIDATE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                return _parse_response(response.text)

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    last_error = e
                    continue
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    last_error = e
                    continue
                else:
                    return {
                        "summary": f"요약 중 오류 발생: {e}",
                        "score": 0
                    }
        continue

    return {
        "summary": f"현재 모든 API 키의 할당량이 소진되었습니다. 잠시 후 다시 시도해 주세요.\n(등록된 키: {len(API_KEYS)}개)",
        "score": 0
    }
