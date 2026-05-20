"""
Gemini API 동작 확인용 최소 예제.

- API 키는 key.env의 GEMINI_API_KEY를 사용한다 (하드코딩 금지).
- google-genai SDK의 실제 호출 형식을 따른다.
  (이전 코드의 client.interactions.create / interaction.outputs[-1].text 는
   존재하지 않는 시그니처였다.)
"""
from google import genai
from config import GEMINI_API_KEY

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY가 key.env에 설정되어 있지 않습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Tell me a short joke about programming.",
)

print(response.text)
