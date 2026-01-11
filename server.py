from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import random
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- إعدادات Genisi ---
BASE_URL = "https://gen.pollinations.ai"

MODEL_CHAT_FAST = "gemini-fast"
MODEL_CHAT_CODE = "gemini-large"

# التعديل هنا: غيرنا "nanobanana-pro" إلى "flux"
# flux هو النموذج المجاني القوي الذي لا يسبب خطأ 403
MODEL_IMAGE = "flux" 

def get_auth_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

def resolve_model(text, has_file, user_mode):
    """
    تحديد النموذج بناءً على طلب المستخدم + المحتوى
    user_mode: 'auto', 'gemini', 'gemini-large'
    """
    text_lower = text.lower()
    
    # 1. أولوية قصوى: هل المستخدم يطلب صورة؟
    image_keywords = ["ارسم", "صورة", "تخيل", "draw", "generate image", "paint"]
    if any(k in text_lower for k in image_keywords):
        return "IMAGE", None

    # 2. إذا حدد المستخدم نموذجاً معيناً يدوياً
    if user_mode == "gemini":
        return "TEXT", MODEL_CHAT_FAST
    elif user_mode == "gemini-large":
        return "TEXT", MODEL_CHAT_CODE
    
    # 3. الوضع التلقائي (Auto Mode)
    code_keywords = ["code", "python", "java", "script", "error", "debug", "function", "api", "كود", "برمجة", "خطأ"]
    if has_file or any(k in text_lower for k in code_keywords):
        return "TEXT", MODEL_CHAT_CODE
    
    return "TEXT", MODEL_CHAT_FAST

def translate_prompt(text):
    try:
        payload = {
            "model": MODEL_CHAT_FAST,
            "messages": [
                {"role": "system", "content": "Translate to English for image prompt. Output ONLY translation."},
                {"role": "user", "content": text}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions", 
            headers=get_auth_headers(), 
            json=payload, 
            timeout=10
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except:
        pass
    return text

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_input = data.get('message', '')
        file_content = data.get('file_content', '')
        file_name = data.get('file_name', '')
        user_mode = data.get('model_mode', 'auto') 

        if not user_input and not file_content:
            return jsonify({"reply": "Empty request"}), 400

        full_context = user_input
        if file_content:
            full_context += f"\n\n--- Attached File: {file_name} ---\n{file_content}\n--- End File ---"

        # تحديد النية والنموذج
        intent, selected_model = resolve_model(user_input, bool(file_content), user_mode)

        # --- معالجة الصور ---
        if intent == "IMAGE":
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 9999999)
            
            image_url = (
                f"{BASE_URL}/image/{encoded_prompt}"
                f"?model={MODEL_IMAGE}&width=1024&height=1024&seed={seed}&nologo=true&key={API_KEY}"
            )
            html_response = (
                f"🎨 <b>Genisi Art (Flux):</b> {user_input}<br>"
                f"<small style='color:#888'>{english_prompt}</small><br>"
                f"<img src='{image_url}' alt='Genisi Image' style='width:100%; border-radius:10px; margin-top:10px;'>"
            )
            return jsonify({"reply": html_response})

        # --- معالجة النصوص/البرمجة ---
        else:
            system_msg = "You are Genisi."
            if selected_model == MODEL_CHAT_CODE:
                system_msg = "You are Genisi Coder . Expert developer. Analyze code deeply."
            else:
                system_msg = "You are Genisi . Fast and helpful assistant."

            payload = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": full_context}
                ],
                "temperature": 0.7
            }

            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=get_auth_headers(),
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                bot_reply = response.json()['choices'][0]['message']['content']
                badge = "⚡ GPT-4o" if selected_model == MODEL_CHAT_FAST else "💻 Qwen-Coder"
                bot_reply = f"`[{badge}]`\n\n{bot_reply}"
                return jsonify({"reply": bot_reply})
            
            return jsonify({"reply": f"Error: {response.status_code}"}), 500

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"reply": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
