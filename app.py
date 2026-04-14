import os
import json
from urllib import error, request as urllib_request
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.json.ensure_ascii = False

SYSTEM_PROMPT = """
你係香港廣東話粗口改寫助手。

任務：將輸入句子改寫成香港人真係會講、自然順口、貼地、有少量粗口嘅版本。

硬規則：
1. 只可以用香港常見廣東話口語。
2. 唔可以用普通話腔、書面語腔、台灣用語。
3. 保留原意，可以改成更貼地、更口語。
4. 只輸出一句結果，唔好解釋，唔好加引號，唔好分點。
5. 粗口要自然，唔好為粗而粗，唔好硬塞。
6. 優先用香港人日常會講嘅句式，而唔係花巧網絡拼字。
7. 語氣可以強烈，但要似真人講嘢，唔好太作狀。

詞彙風格偏好（可自然使用）：
- 屌
- 大癲
- 好撚7
- Sor9ly
- 好Kam
- 屌你老母好撚正啊
- 好撫好食（當語氣化寫法使用）

用法要求：
1. 詞彙要按語境自然出現，唔好每句都硬塞。
2. 如果句子係稱讚、驚嘆，可偏向「屌你老母好撚正啊」、「好撚7」、「大癲」。
3. 如果句子係輕微道歉，可用「Sor9ly」。
4. 保持香港網民口吻，但句子仍要可讀、順口。

示範：
輸入：你好聰明啊
輸出：你真係撚醒目喎

輸入：呢間餐廳好好食
輸出：屌，好撫好食

輸入：呢個位真係勁
輸出：屌你老母好撚正啊

輸入：我搞錯咗
輸出：Sor9ly，我啱啱搞錯咗

輸入：呢件事太離譜
輸出：好撚7，成件事真係大癲

輸入：謝謝你幫我
輸出：唔該晒你幫手，真係多謝晒

輸入：對不起，我遲到了
輸出：唔好意思，我遲撚咗到

輸入：你不要再這樣做了
輸出：你唔好再咁撚樣搞落去啦

輸入：你今天怎麼這麼慢
輸出：你今日做乜鳩咁慢啊

輸入：這個東西真的很好笑
輸出：呢樣嘢真係笑撚死我

輸入：我真的很生氣
輸出：我真係火都嚟撚埋

輸入：你可不可以快一點
輸出：你可唔可以快撚啲啊

輸入：這也太誇張了吧
輸出：呢鋪都誇撚張得滯啦下話

輸入：我不知道該怎麼辦
輸出：我而家真係唔撚知點搞好

輸入：你說得很對
輸出：你咁講又真係幾撚啱

輸入：這件事很麻煩
輸出：呢單嘢真係麻撚煩到痴線

輸入：我快要瘋了
輸出：我就快俾呢單嘢搞到癲撚咗

輸入：為什麼又是我
輸出：做乜撚嘢又係我啊
""".strip()

CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_MODEL = os.environ.get("CLOUDFLARE_MODEL", "@cf/google/gemma-4-26b-a4b-it")


def get_missing_config():
    missing = []
    if not CLOUDFLARE_API_TOKEN:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not CLOUDFLARE_ACCOUNT_ID:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    return missing


missing_config = get_missing_config()
if missing_config:
    print(f"Warning: missing Cloudflare config: {', '.join(missing_config)}")


def call_workers_ai(prompt):
    missing = get_missing_config()
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/v1/chat/completions"
    )
    payload = {
        "model": CLOUDFLARE_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.45,
        "max_completion_tokens": 300,
        "chat_template_kwargs": {
            "enable_thinking": False,
        },
    }
    req = urllib_request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=60) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(details) from exc
    except error.URLError as exc:
        raise RuntimeError(str(exc)) from exc

    choices = response_data.get("choices") or []
    if not choices:
        raise RuntimeError(json.dumps(response_data, ensure_ascii=False))

    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
        content = "".join(text_parts).strip()

    if content:
        return str(content).strip()

    refusal = message.get("refusal")
    if refusal:
        return str(refusal).strip()

    raise RuntimeError(json.dumps(response_data, ensure_ascii=False))


def ensure_text_growth(original_text, generated_text):
    if len(generated_text) > len(original_text):
        return generated_text

    # 最後保底：優先用語氣助詞擴寫，避免生硬尾綴
    particles = ["啦", "喎", "呀", "囉"]
    particle = particles[len(original_text) % len(particles)]
    stripped = generated_text.rstrip()
    if stripped.endswith(("。", "！", "？", "!", "?")):
        return f"{stripped[:-1]}{particle}{stripped[-1]}"
    return f"{generated_text}{particle}"


@app.route('/')
def index():
    return render_template('index.html')

# 讓 Flask 提供 style.css 靜態檔案
@app.route('/templates/style.css')
def serve_css():
    return send_from_directory('templates', 'style.css')

@app.route('/images/<path:filename>')
def serve_image(filename):
    # 允許存取根目錄下的 images 資料夾
    return send_from_directory('images', filename)

@app.route('/insert_profanity', methods=['POST'])
def insert_profanity():
    data = request.get_json()
    user_text = data.get('text', '')

    if not user_text:
        return jsonify({'result': ''})

    # 建構 Prompt
    prompt = f"""
    將下面句子改寫成香港網民口吻、自然廣東話、順口又貼地嘅版本。

    要求：
    - 保留原意
    - 用香港人自然口語，避免作狀網絡拼字
    - 可有粗口，但要自然唔生硬
    - 輸出字數必須比輸入至少多 1 個字
    - 只輸出一句
    - 唔好解釋

    輸入：{user_text}
    輸出：
    """

    try:
        modified_text = ""
        retry_prompts = [
            prompt,
            f"{prompt}\n注意：上次輸出太短。今次要自然口語擴寫，最少多 2 個字。",
            f"{prompt}\n注意：可加語氣詞（例如：啦、喎、呀），但要似香港人自然講法。",
        ]

        for retry_prompt in retry_prompts:
            candidate = call_workers_ai(retry_prompt)
            if len(candidate) > len(user_text):
                modified_text = candidate
                break
            modified_text = candidate

        modified_text = ensure_text_growth(user_text, modified_text)
        return jsonify({'result': modified_text})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'AI 處理失敗，請檢查 Cloudflare Workers AI 設定或網絡連線'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
