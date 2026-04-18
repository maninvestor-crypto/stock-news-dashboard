import os
from google import genai
from dotenv import load_dotenv, find_dotenv

# .env 파일을 안전하게 로드
load_dotenv(find_dotenv(), override=True)

# ─── API 키 목록 수집 ────────────────────────────────────────────────────────
# 환경변수에서 GEMINI_API_KEY, GEMINI_API_KEY_1, GEMINI_API_KEY_2 … 순서로 모두 수집
def _collect_api_keys():
    keys = []
    # 단일 키 (기본)
    k = os.getenv("GEMINI_API_KEY", "").strip()
    if k:
        keys.append(k)
    # 번호 키 1~10
    for i in range(1, 11):
        k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    # 중복 제거 (순서 유지)
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
    if not text and fallback_title:
        return f"""해당 뉴스 기사의 본문 접근이 차단되어 본문을 읽을 수 없습니다.
하지만 다음은 기사의 '제목'입니다. 제목을 바탕으로 이 뉴스가 어떤 핵심 이슈를 다루고 있는지 '- ' 로 시작하는 글머리 기호 3줄 이하로 간략히 추론하여 요약해 주세요.

기사 제목: {fallback_title}"""
    elif text:
        return f"""다음은 증권 관련 뉴스 기사의 본문입니다.
이 기사에서 다루는 가장 중요한 핵심 이슈를 '- ' 로 시작하는 글머리 기호(bullet points) 형식으로 요약해 주세요.
반드시 3줄 이하로만 대답하세요.

기사 본문:
{text}"""
    return None

def summarize_text(text, fallback_title=""):
    """기사 본문을 입력받아 3줄 이내로 요약합니다.
    - 등록된 API 키를 순서대로 시도합니다.
    - 할당량 초과(429) 시 다음 키로 자동 전환합니다.
    - 각 키마다 사용 가능한 모델을 순서대로 시도합니다.
    """
    if not API_KEYS:
        return "API 키가 설정되지 않아 요약 기능을 사용할 수 없습니다. `.env` 파일을 확인해 주세요."

    prompt = _build_prompt(text, fallback_title)
    if prompt is None:
        return "기사 본문과 제목을 모두 가져올 수 없습니다."

    last_error = None

    for api_key in API_KEYS:
        client = genai.Client(api_key=api_key)

        for model_name in CANDIDATE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                return response.text

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # 이 키/모델 할당량 초과 → 다음 모델 시도
                    last_error = e
                    continue
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    # 모델 미지원 → 다음 모델 시도
                    last_error = e
                    continue
                else:
                    # 그 외 오류(인증 실패 등)는 즉시 반환
                    return f"요약 중 오류 발생: {e}"

        # 이 키의 모든 모델이 할당량 초과 → 다음 키로 전환
        continue

    return (
        f"현재 모든 API 키의 할당량이 소진되었습니다. 잠시 후 다시 시도해 주세요.\n"
        f"(등록된 키: {len(API_KEYS)}개 / 마지막 오류: {last_error})"
    )
