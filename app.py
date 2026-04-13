import os
import json
from urllib import error, request as urllib_request
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.json.ensure_ascii = False

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
                "content": "你係一個熟悉香港廣東話粗口語感嘅助手，輸出必須自然、口語、直接。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 1,
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
    任務：將廣東話粗口（如：撚、鳩、柒、屌、仆街、含家鏟等）插入到用戶提供的句子中，並確保全句使用道地廣東話口語。
    
    規則：
    1. **語境分析與口語化**：
       - 先分析句子的語境（例如：是感謝幫忙還是感謝禮物？是輕微道歉還是嚴重過失？）。
       - 將書面語/普通話轉換為**最貼切**的廣東話口語。
       - *關鍵要求*：必須根據語境自動選擇正確的用詞（例如：「謝謝」若指服務應轉為「唔該」，指禮物應轉為「多謝」；「對不起」若指借過應轉為「唔好意思」）。
    2. **插入粗口**：
       - 在最順口的位置（通常是形容詞前、動詞後、或助詞前）插入一個廣東話粗口（如：撚、鳩、柒、屌、仆街）。
       - 也可以將雙字詞拆開插入（例如：多謝 -> 多撚謝）。
    3. **輸出規則**：
       - 保持原意，但語氣要更強烈、更地道。
       - 直接輸出改寫後的句子，不要解釋。
    
    用戶句子：{user_text}
    """

    try:
        modified_text = call_workers_ai(prompt)
        return jsonify({'result': modified_text})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'AI 處理失敗，請檢查 Cloudflare Workers AI 設定或網絡連線'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
