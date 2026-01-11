from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import random
import urllib.parse

# إعداد السجلات لمراقبة الأخطاء
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- إعدادات Genisi ---
API_KEY = "sk_JHTVJDFsV7uiHdMVFqNKwzY8DZkhw0Oz"  # مفتاحك الخاص
TEXT_MODEL = "gemini"             # النموذج النصي والترجمة
IMAGE_MODEL = "nanobanana-pro"    # نموذج الصور القوي
BASE_URL = "https://gen.pollinations.ai"

# الكلمات المفتاحية التي تدل على طلب صورة
IMAGE_KEYWORDS = ["ارسم", "صورة", "تخيل", "رسمة", "ولد", "draw", "image", "generate", "paint"]

def get_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

def translate_to_english(text):
    """
    وظيفة لترجمة النص العربي إلى إنجليزي لضمان دقة الصورة
    نستخدم نفس نموذج gemini للقيام بهذه المهمة
    """
    try:
        payload = {
            "model": TEXT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a translator. Translate the following Arabic image description into a detailed English prompt for an AI image generator. Output ONLY the English translation, nothing else."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            "temperature": 0.3
        }
        
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions", 
            json=payload, 
            headers=get_headers(),
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        return text # في حال الفشل نعود للنص الأصلي
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        return text

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_input = data.get('message', '')
        
        if not user_input:
            return jsonify({"reply": "الرجاء كتابة رسالة."}), 400

        logger.info(f"User Input: {user_input}")

        # --- المنطق 1: هل يريد المستخدم صورة؟ ---
        # نفحص هل تحتوي الرسالة على كلمات رسم
        is_image_request = any(keyword in user_input.lower() for keyword in IMAGE_KEYWORDS)

        if is_image_request:
            # 1. ترجمة الطلب للإنجليزية للحصول على أفضل نتيجة
            english_prompt = translate_to_english(user_input)
            logger.info(f"Translated Prompt: {english_prompt}")
            
            # 2. تجهيز رابط الصورة (تشفير النص ليكون صالحاً في الرابط)
            safe_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 1000000) # رقم عشوائي لتغيير النتيجة كل مرة
            
            # رابط الصورة المباشر
            image_url = f"{BASE_URL}/image/{safe_prompt}?model={IMAGE_MODEL}&width=1024&height=1024&seed={seed}&nologo=true"
            
            # إرجاع الصورة بتنسيق HTML ليفهمها المتصفح
            reply_html = (
                f"🎨 <b>جاري رسم خيالك:</b> {user_input}<br>"
                f"<img src='{image_url}' alt='Genisi Image' style='width: 100%; border-radius: 15px; margin-top: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'>"
            )
            return jsonify({"reply": reply_html})

        # --- المنطق 2: محادثة نصية عادية (Gemini) ---
        else:
            payload = {
                "model": TEXT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "أنت Genisi، مساعد ذكي ومبدع. تتحدث العربية بطلاقة. ردودك مفيدة ومختصرة."
                    },
                    {
                        "role": "user",
                        "content": user_input
                    }
                ]
            }

            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                headers=get_headers(),
                timeout=40
            )

            if response.status_code == 200:
                try:
                    api_data = response.json()
                    bot_reply = api_data['choices'][0]['message']['content']
                    return jsonify({"reply": bot_reply})
                except Exception:
                    # في حال لم يكن الرد JSON (احتياط)
                    return jsonify({"reply": response.text})
            else:
                logger.error(f"API Error: {response.text}")
                return jsonify({"reply": "عذراً، واجهت مشكلة في الاتصال بنموذج Gemini."}), 500

    except Exception as e:
        logger.error(f"Fatal Error: {e}")
        return jsonify({"reply": "حدث خطأ غير متوقع في الخادم."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
