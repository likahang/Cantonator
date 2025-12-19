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
