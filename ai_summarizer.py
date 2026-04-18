import os
from google import genai
from dotenv import load_dotenv, find_dotenv

# .env 파일을 물리적으로 찾아 안전하게 로드합니다. (파일이 없으면 무시)
load_dotenv(find_dotenv(), override=True)

api_key = os.getenv("GEMINI_API_KEY")

# 무료 티어에서 사용 가능한 모델 우선순위 목록 (순서대로 시도)
# 무겁고 비싼 모델일수록 뒤에 배치
CANDIDATE_MODELS = [
    "gemini-2.0-flash-lite",   # 무료 티어 최우선 (가장 가볍고 빠름)
    "gemini-2.0-flash-lite-001",
    "gemini-2.0-flash",        # 중간 성능
    "gemini-2.0-flash-001",
    "gemini-2.5-flash",        # 최고 성능 (할당량 소진 시 폴백)
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
    """기사 본문을 입력받아 3줄 이내로 요약합니다. 모델 할당량 초과 시 다음 모델로 자동 전환합니다."""
    if not api_key:
        return "API 키가 설정되지 않아 요약 기능을 사용할 수 없습니다. `.env` 파일을 확인해 주세요."

    prompt = _build_prompt(text, fallback_title)
    if prompt is None:
        return "기사 본문과 제목을 모두 가져올 수 없습니다."

    client = genai.Client(api_key=api_key)
    last_error = None

    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            err_str = str(e)
            # 할당량 초과(429) 또는 모델 미지원(404)인 경우 다음 모델로 전환
            if "429" in err_str or "404" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                last_error = e
                continue
            else:
                # 그 외 오류는 즉시 반환
                return f"요약 중 오류 발생: {e}"

    return f"현재 사용 가능한 모델이 없습니다. 잠시 후 다시 시도해 주세요.\n(마지막 오류: {last_error})"
