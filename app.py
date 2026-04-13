import os
import json
from urllib import error, request as urllib_request
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.json.ensure_ascii = False

SYSTEM_PROMPT = """
你係香港廣東話粗口改寫助手。

任務：將輸入句子改寫成香港人真係會講、自然順口、帶粗口或網絡化語感嘅版本。

硬規則：
1. 只可以用香港常見廣東話口語、粗口、網絡語感。
2. 唔可以用普通話腔、書面語腔、台灣用語。
3. 保留原意，但容許改成更貼地、更串嘴、更有火氣嘅講法。
4. 只輸出一句結果，唔好解釋，唔好加引號，唔好分點。
5. 粗口要自然，唔好為粗而粗。
6. 必須優先模仿香港網民真實會寫、會講嘅語感，而唔係字面直譯。
7. 如果有更貼地嘅講法，可以大幅改寫字面，只要原意仲喺度。

示範：
輸入：你好聰明啊
輸出：你真係撚醒目喎

輸入：謝謝你幫我
輸出：唔該晒你幫我手，真係多撚謝

輸入：對不起，我遲到了
輸出：Sor9;y，我遲撚大到

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
        "temperature": 0.55,
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
    - 可以使用粗口、變體字、網絡寫法
    - 只輸出一句
    - 唔好解釋

    輸入：{user_text}
    輸出：
    """

    try:
        modified_text = call_workers_ai(prompt)
        return jsonify({'result': modified_text})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'AI 處理失敗，請檢查 Cloudflare Workers AI 設定或網絡連線'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
