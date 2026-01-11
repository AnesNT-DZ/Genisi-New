from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import random
import urllib.parse
import traceback

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- الإعدادات (بدون مفتاح API لضمان المجانية) ---
# نستخدم الرابط الموحد للنصوص لأنه يدعم اختيار gemini بدقة
TEXT_API_URL = "https://text.pollinations.ai/" 
# نستخدم رابط الصور الكلاسيكي (القديم والمستقر)
IMAGE_BASE_URL = "https://image.pollinations.ai/prompt"

# --- النماذج المختارة ---
MODEL_TEXT = "gemini"  # قوي في البرمجة والدردشة
MODEL_IMAGE = "flux"   # أفضل نموذج صور مجاني

def resolve_intent(text, has_file):
    """تحديد هل المستخدم يريد صورة أم نص"""
    text_lower = text.lower()
    
    # كلمات مفتاحية للصور
    image_keywords = ["ارسم", "صورة", "تخيل", "draw", "generate image", "paint", "رسمة"]
    if any(k in text_lower for k in image_keywords):
        return "IMAGE"
    
    # الباقي يعتبر نصوص/برمجة (gemini يتكفل بالأمرين)
    return "TEXT"

def translate_prompt(text):
    """ترجمة وصف الصورة للإنجليزية باستخدام Gemini"""
    try:
        payload = {
            "model": MODEL_TEXT,
            "messages": [
                {"role": "system", "content": "Translate the following image description to English. Output ONLY the translation, no extra text."},
                {"role": "user", "content": text}
            ],
            "temperature": 0.3
        }
        # لا نرسل أي Headers للتوثيق (Anonymous)
        response = requests.post(TEXT_API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return response.text # text endpoint يعيد النص مباشرة غالباً
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
        file_content = data.get('file_content', '')
        file_name = data.get('file_name', '')

        if not user_input and not file_content:
            return jsonify({"reply": "Empty request"}), 400

        # دمج الملف مع الرسالة (Gemini ممتاز في قراءة السياق الطويل)
        full_context = user_input
        if file_content:
            full_context += f"\n\n[Attached File: {file_name}]\n{file_content}\n[End of File]"

        # تحديد النية
        intent = resolve_intent(user_input, bool(file_content))

        # ==========================================
        # 🎨 مسار الصور (Flux)
        # ==========================================
        if intent == "IMAGE":
            # 1. ترجمة الوصف
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 99999999)
            
            # 2. إنشاء الرابط (Flux مجاني ولا يحتاج مفتاح)
            image_url = (
                f"{IMAGE_BASE_URL}/{encoded_prompt}"
                f"?model={MODEL_IMAGE}"
                f"&width=1024&height=1024"
                f"&seed={seed}"
                f"&nologo=true"
            )
            
            html_response = (
                f"🎨 <b>Genisi Art (Flux):</b> {user_input}<br>"
                f"<small style='color:#888'>{english_prompt}</small><br>"
                f"<img src='{image_url}' alt='Generating...' style='width:100%; border-radius:10px; margin-top:10px; box-shadow:0 5px 15px rgba(0,0,0,0.3);'>"
            )
            return jsonify({"reply": html_response})

        # ==========================================
        # 💻 مسار النصوص والبرمجة (Gemini)
        # ==========================================
        else:
            payload = {
                "model": MODEL_TEXT, # gemini
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are Genisi. An expert AI assistant powered by Gemini. You are excellent at coding, debugging, and general conversation. Answer in the same language as the user."
                    },
                    {
                        "role": "user", 
                        "content": full_context
                    }
                ],
                "temperature": 0.7,
                "stream": False
            }

            # إرسال الطلب بدون Headers (مجاني)
            response = requests.post(TEXT_API_URL, json=payload, timeout=60)

            if response.status_code == 200:
                # محاولة استخراج النص (قد يكون JSON أو Plain Text)
                try:
                    # أحياناً text endpoint يعيد نص خام
                    bot_reply = response.text 
                    # تنظيف الرد إذا كان يحتوي على JSON string بالخطأ
                    if bot_reply.strip().startswith('{') and '"content":' in bot_reply:
                         import json
                         json_data = json.loads(bot_reply)
                         if 'choices' in json_data:
                             bot_reply = json_data['choices'][0]['message']['content']
                except:
                    bot_reply = response.text

                # إضافة بادئة لتوضيح النموذج
                bot_reply = f"`[💎 Gemini]`\n\n{bot_reply}"
                return jsonify({"reply": bot_reply})
            
            else:
                return jsonify({"reply": f"Error from Pollinations: {response.status_code} - {response.text}"}), 500

    except Exception as e:
        logger.error(f"Fatal Error: {e}")
        traceback.print_exc()
        return jsonify({"reply": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
