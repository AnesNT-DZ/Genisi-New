from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import random
import urllib.parse

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- الإعدادات بناءً على التوثيق ---
API_KEY = "sk_JHTVJDFsV7uiHdMVFqNKwzY8DZkhw0Oz"
BASE_URL = "https://gen.pollinations.ai"

# --- النماذج المذكورة في التوثيق ---
MODEL_CHAT_FAST = "openai"          # النموذج السريع (General)
MODEL_CHAT_CODE = "qwen-coder"      # النموذج المخصص للبرمجة
MODEL_IMAGE = "nanobanana-pro"      # نموذج الصور القوي

def get_auth_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

def detect_intent_and_model(text, has_file):
    """تحديد النية واختيار النموذج المناسب"""
    text_lower = text.lower()
    
    # كلمات تدل على الصور
    image_keywords = ["ارسم", "صورة", "تخيل", "draw", "generate image", "paint"]
    if any(k in text_lower for k in image_keywords):
        return "IMAGE", None

    # كلمات تدل على البرمجة أو وجود ملف
    code_keywords = ["code", "python", "java", "script", "error", "debug", "function", "api", "كود", "برمجة", "خطأ"]
    if has_file or any(k in text_lower for k in code_keywords):
        return "TEXT", MODEL_CHAT_CODE
    
    # الافتراضي: دردشة سريعة
    return "TEXT", MODEL_CHAT_FAST

def translate_prompt(text):
    """ترجمة وصف الصورة للإنجليزية لضمان الدقة"""
    try:
        # نستخدم endpoint الشات للترجمة
        payload = {
            "model": MODEL_CHAT_FAST,
            "messages": [
                {"role": "system", "content": "Translate the following to English for an image prompt. Output ONLY the translation."},
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
    except Exception as e:
        logger.error(f"Translation failed: {e}")
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

        if not user_input and not file_content:
            return jsonify({"reply": "Empty request"}), 400

        # دمج الملف مع الرسالة
        full_context = user_input
        if file_content:
            full_context += f"\n\n--- Attached File: {file_name} ---\n{file_content}\n--- End File ---"

        # تحديد النية
        intent, selected_model = detect_intent_and_model(user_input, bool(file_content))
        
        # ---------------------------------------------
        # 1. معالجة الصور (Image Generation)
        # ---------------------------------------------
        if intent == "IMAGE":
            # ترجمة الوصف
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 9999999)
            
            # بناء الرابط حسب التوثيق: GET /image/{prompt}
            # الحل الجذري للـ 401: تمرير key في الرابط
            image_url = (
                f"{BASE_URL}/image/{encoded_prompt}"
                f"?model={MODEL_IMAGE}"
                f"&width=1024&height=1024"
                f"&seed={seed}"
                f"&nologo=true"
                f"&key={API_KEY}"  # <--- هذا هو الإصلاح حسب التوثيق
            )
            
            html_response = (
                f"🎨 <b>Genisi Art:</b> {user_input}<br>"
                f"<small style='color:#888'>Translated: {english_prompt}</small><br>"
                f"<img src='{image_url}' alt='Generating...' style='width:100%; border-radius:10px; margin-top:10px; box-shadow:0 5px 15px rgba(0,0,0,0.3);'>"
            )
            return jsonify({"reply": html_response})

        # ---------------------------------------------
        # 2. معالجة النصوص والبرمجة (Text/Code Generation)
        # ---------------------------------------------
        else:
            system_msg = "You are Genisi."
            if selected_model == MODEL_CHAT_CODE:
                system_msg = "You are an expert Coding Assistant (Genisi Coder). Analyze the code, fix errors, and explain clearly."
            else:
                system_msg = "You are Genisi, a fast and helpful assistant."

            # الهيكلة حسب التوثيق POST /v1/chat/completions
            payload = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": full_context}
                ],
                "temperature": 0.7,
                "stream": False
            }

            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=get_auth_headers(),
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                # استخراج الرد حسب بنية OpenAI
                bot_reply = data['choices'][0]['message']['content']
                
                # إضافة توقيع النموذج المستخدم للمطور
                model_badge = "⚡ Fast" if selected_model == MODEL_CHAT_FAST else "👨‍💻 Coder"
                bot_reply = f"`[{model_badge}]`\n\n{bot_reply}"
                
                return jsonify({"reply": bot_reply})
            
            elif response.status_code == 401:
                return jsonify({"reply": "خطأ 401: مفتاح API غير صالح أو انتهت صلاحيته."}), 401
            else:
                logger.error(f"API Error: {response.text}")
                return jsonify({"reply": f"Error from Pollinations: {response.status_code}"}), 500

    except Exception as e:
        logger.error(f"Server Error: {e}")
        return jsonify({"reply": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
