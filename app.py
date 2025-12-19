import os
from flask import Flask, render_template, request, jsonify, send_from_directory
import google.generativeai as genai

app = Flask(__name__)

# 設定你的 Google API Key
# ⚠️ 安全警告：部署到 GitHub 時，切勿將真實的 API Key 硬編碼在程式碼中！
# 請在部署平台 (如 Render, Railway, Heroku) 的 Environment Variables 中設定 GOOGLE_API_KEY
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    # 本地測試時，如果沒有設定環境變數，請自行處理 (但不要 Commit 真實 Key 到 GitHub)
    print("Warning: GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=api_key)

# 設定安全過濾器
# 針對粗口生成應用，必須將過濾器設為 BLOCK_NONE，否則 API 會拒絕生成
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    },
]

# 使用最新的 Gemini 3 Flash 模型
# 更新日期：2025-12-18
model = genai.GenerativeModel(
    model_name='gemini-3-flash-preview',  # 更新為最新的模型名稱
    safety_settings=safety_settings
)

@app.route('/')
def index():
    return render_template('index.html')

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
    # Gemini 3 Flash 對指令的理解能力更強，我們可以稍微精簡 Prompt，但保持核心規則
    prompt = f"""
    任務：將廣東話粗口（如：撚、鳩、柒、屌、仆街、含家鏟等）插入到用戶提供的句子中，並確保全句使用道地廣東話口語。
    
    規則：
    1. **口語化轉換**：首先將句子中的書面語或普通話用詞轉換為道地的廣東話口語（例如：將「帥」改為「靚仔」、將「什麼」改為「咩」、將「很」改為「好」）。
    2. **插入粗口**：在轉換後的句子中，插入**一個**新的粗口字或詞。
    3. 必須保持句子原本的語意通順。
    4. 如果句子已經包含粗口，請在其他位置增加一個，或加強語氣。
    5. 直接輸出修改後的句子，不要包含任何解釋或標記。
    
    用戶句子：{user_text}
    """

    try:
        # Gemini 3 Flash 的回應速度極快，適合即時互動
        response = model.generate_content(prompt)
        
        # 取得回應文字
        modified_text = response.text.strip()
        return jsonify({'result': modified_text})
    except Exception as e:
        print(f"Error: {e}")
        # 捕捉錯誤，例如 API Key 權限不足或模型名稱錯誤
        return jsonify({'error': 'AI 處理失敗，請檢查 API Key 或網絡連線'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
