from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import random
import urllib.parse
import traceback

# إعداد السجلات لرؤية الأخطاء في Render Logs
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- إعدادات Genisi ---
API_KEY = "sk_JHTVJDFsV7uiHdMVFqNKwzY8DZkhw0Oz"
BASE_URL = "https://gen.pollinations.ai"

# --- النماذج ---
MODEL_CHAT_FAST = "openai"
MODEL_CHAT_CODE = "qwen-coder"
MODEL_IMAGE = "nanobanana-pro"
MODEL_VIDEO = "veo"

def get_auth_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

def resolve_model(text, has_file, user_mode):
    """تحديد النية واختيار النموذج"""
    try:
        text_lower = text.lower()
        
        # 1. الاختيار اليدوي
        if user_mode == "veo": return "VIDEO", MODEL_VIDEO
        if user_mode == "openai": return "TEXT", MODEL_CHAT_FAST
        if user_mode == "qwen-coder": return "TEXT", MODEL_CHAT_CODE
        
        # 2. الوضع التلقائي
        video_keywords = ["video", "movie", "clip", "فيديو", "مقطع", "فيلم"]
        if any(k in text_lower for k in video_keywords): return "VIDEO", MODEL_VIDEO

        image_keywords = ["ارسم", "صورة", "تخيل", "draw", "generate image", "paint"]
        if any(k in text_lower for k in image_keywords): return "IMAGE", MODEL_IMAGE

        code_keywords = ["code", "python", "java", "html", "error", "debug", "api", "كود", "برمجة"]
        if has_file or any(k in text_lower for k in code_keywords): return "TEXT", MODEL_CHAT_CODE
        
        return "TEXT", MODEL_CHAT_FAST
    except Exception as e:
        print(f"Error in resolve_model: {e}")
        return "TEXT", MODEL_CHAT_FAST

def translate_prompt(text):
    """ترجمة آمنة - إذا فشلت تعيد النص الأصلي بدلاً من تحطيم السيرفر"""
    try:
        payload = {
            "model": MODEL_CHAT_FAST,
            "messages": [
                {"role": "system", "content": "Translate to English. Output ONLY translation."},
                {"role": "user", "content": text}
            ]
        }
        # timeout قصير لتجنب تعليق السيرفر
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions", 
            headers=get_auth_headers(), 
            json=payload, timeout=5 
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Translation Warning: {e}") # طباعة تحذير فقط
    
    return text # في حال الفشل، نستخدم النص العربي كما هو

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # استقبال البيانات
        data = request.json
        if not data:
            return jsonify({"reply": "No data received"}), 400

        user_input = data.get('message', '')
        file_content = data.get('file_content', '')
        file_name = data.get('file_name', '')
        user_mode = data.get('model_mode', 'auto')

        if not user_input and not file_content:
            return jsonify({"reply": "Empty request"}), 400

        full_context = user_input
        if file_content:
            full_context += f"\n\nFile: {file_name}\n{file_content}"

        # تحديد النموذج
        intent, selected_model = resolve_model(user_input, bool(file_content), user_mode)
        print(f"Processing: Intent={intent}, Model={selected_model}") # Log for debugging

        # --- معالجة الفيديو ---
        if intent == "VIDEO":
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 999999)
            
            video_url = (
                f"{BASE_URL}/image/{encoded_prompt}"
                f"?model={MODEL_VIDEO}"
                f"&seed={seed}&width=1024&height=576&aspectRatio=16:9&key={API_KEY}"
            )
            html_response = (
                f"🎥 <b>Genisi Veo:</b> {user_input}<br>"
                f"<small style='color:#888'>{english_prompt}</small><br>"
                f"<video controls autoplay loop src='{video_url}' style='width:100%; border-radius:10px; margin-top:10px;'></video>"
            )
            return jsonify({"reply": html_response})

        # --- معالجة الصور ---
        elif intent == "IMAGE":
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 999999)
            
            image_url = (
                f"{BASE_URL}/image/{encoded_prompt}"
                f"?model={MODEL_IMAGE}&width=1024&height=1024&seed={seed}&nologo=true&key={API_KEY}"
            )
            html_response = (
                f"🎨 <b>Genisi Art:</b> {user_input}<br>"
                f"<small style='color:#888'>{english_prompt}</small><br>"
                f"<img src='{image_url}' alt='Generating...' style='width:100%; border-radius:10px; margin-top:10px;'>"
            )
            return jsonify({"reply": html_response})

        # --- معالجة النصوص ---
        else:
            system_msg = "You are Genisi."
            if selected_model == MODEL_CHAT_CODE:
                system_msg = "You are Genisi Coder (Qwen). Expert developer."
            else:
                system_msg = "You are Genisi (OpenAI). Fast assistant."

            payload = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": full_context}
                ],
                "temperature": 0.7
            }

            # زيادة مهلة الانتظار لتجنب Timeout
            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=get_auth_headers(),
                json=payload, timeout=45
            )

            if response.status_code == 200:
                try:
                    # محاولة قراءة JSON بأمان
                    data_json = response.json()
                    bot_reply = data_json['choices'][0]['message']['content']
                except Exception:
                    # إذا فشل JSON، نأخذ النص كما هو (Pollinations أحياناً ترسل نصاً فقط)
                    bot_reply = response.text
                
                badge = "⚡ GPT-4o" if selected_model == MODEL_CHAT_FAST else "💻 Qwen-Coder"
                bot_reply = f"`[{badge}]`\n\n{bot_reply}"
                return jsonify({"reply": bot_reply})
            
            else:
                print(f"External API Error: {response.status_code} - {response.text}")
                return jsonify({"reply": f"عذراً، حدث خطأ من المصدر: {response.status_code}"}), 500

    except Exception as e:
        # هنا يتم التقاط الخطأ 500 وطباعته في Logs
        print("FATAL ERROR IN CHAT ENDPOINT:")
        traceback.print_exc() # هذا السطر مهم جداً، يطبع تفاصيل الخطأ كاملة
        return jsonify({"reply": "حدث خطأ داخلي في الخادم (Internal Error)."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
