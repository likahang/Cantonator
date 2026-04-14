import os
import json
from urllib import error, request as urllib_request
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.json.ensure_ascii = False

SYSTEM_PROMPT = """
你係香港廣東話粗口遞增改寫助手。

任務：每次將輸入句子改寫成剛好多 1 個粗口詞嘅版本，令粗口數量逐步遞增。

硬規則：
1. 只可以用香港常見廣東話口語。
2. 唔可以用普通話腔、書面語腔、台灣用語。
3. 保留原意，可以改成更貼地、更口語嘅句式。
4. 只輸出一句結果，唔好解釋，唔好加引號，唔好分點。
5. 新粗口詞必須自然融入句子，唔好硬塞。
6. 語氣要似真人講嘢，要順口。
7. 如有需要，可以合理擴展句子令新粗口有合適語境。

可用粗口詞參考（按語境選用，唔限於此）：
屌、閪、撚、鳩、柒、仆街、冚家剷、炒、撚樣、大癲

遞增示範：
0→1：呢碟嘢好食 → 呢碟嘢真係好撚食
1→2：呢碟嘢真係好撚食 → 屌，呢碟嘢真係好撚食
2→3：屌，呢碟嘢真係好撚食 → 屌，呢碟閪嘢真係好撚食
3→4：屌，呢碟閪嘢真係好撚食 → 屌，呢碟閪嘢真係好撚食，食到我忍唔住鳩叫
4→5：屌，呢碟閪嘢真係好撚食，食到我忍唔住鳩叫 → 屌，呢碟閪嘢真係好撚食，食到我成個柒頭咁喺度鳩叫
""".strip()

CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_MODEL = os.environ.get("CLOUDFLARE_MODEL", "@cf/google/gemma-4-26b-a4b-it")

NORMALIZATION_REPLACEMENTS = {
    "好撫好食": "好好食",
    "撫好食": "好食",
}


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
        "temperature": 0.65,
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


def normalize_generated_text(text):
    # 修正模型偶發的怪字詞，避免不自然輸出
    normalized = text
    for wrong, right in NORMALIZATION_REPLACEMENTS.items():
        normalized = normalized.replace(wrong, right)
    return normalized


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
    current_count = int(data.get('profanity_count', 0))
    target_count = current_count + 1

    if not user_text:
        return jsonify({'result': ''})

    base_instruction = (
        f"句子目前有 {current_count} 個粗口詞。"
        f"請加入 1 個新粗口詞，將句子改寫成共有 {target_count} 個粗口詞嘅版本。"
        "新粗口詞要自然融入句子，如有需要可以合理擴展句子結構。"
    )

    retry_prompts = [
        f"{base_instruction}\n\n輸入：{user_text}\n輸出（共 {target_count} 個粗口詞）：",
        f"{base_instruction}\n請確保新粗口詞係額外新增，唔係替換原有嘅。\n\n輸入：{user_text}\n輸出（共 {target_count} 個粗口詞）：",
        f"輸入句子有 {current_count} 個粗口詞，請喺適當位置加入 1 個粗口詞（如屌、閪、撚、鳩、柒、仆街等），令總共有 {target_count} 個。\n\n輸入：{user_text}\n輸出：",
    ]

    try:
        result = user_text
        for prompt in retry_prompts:
            candidate = call_workers_ai(prompt)
            candidate = normalize_generated_text(candidate)
            if candidate and candidate != user_text:
                result = candidate
                break

        return jsonify({'result': result})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'AI 處理失敗，請檢查 Cloudflare Workers AI 設定或網絡連線'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
