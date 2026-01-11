from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import random
import urllib.parse
import traceback
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- إعدادات Genisi ---
TEXT_API_URL = "https://text.pollinations.ai/" 
IMAGE_BASE_URL = "https://image.pollinations.ai/prompt"

MODEL_TEXT = "gemini" 
MODEL_IMAGE = "flux"

def resolve_intent(text):
    """تحديد النية"""
    text_lower = text.lower()
    image_keywords = ["ارسم", "صورة", "تخيل", "draw", "generate image", "paint", "رسمة"]
    if any(k in text_lower for k in image_keywords):
        return "IMAGE"
    return "TEXT"

def translate_prompt(text):
    """ترجمة الوصف باستخدام Gemini"""
    try:
        payload = {
            "model": MODEL_TEXT,
            "messages": [
                {"role": "system", "content": "Translate the following image description to English. Output ONLY the translation."},
                {"role": "user", "content": text}
            ],
            "temperature": 0.3
        }
        response = requests.post(TEXT_API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return response.text
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
        # نستقبل سجل المحادثة السابق من المتصفح
        history = data.get('history', []) 
        
        file_content = data.get('file_content', '')
        file_name = data.get('file_name', '')

        if not user_input and not file_content:
            return jsonify({"reply": "..."}), 400

        # تجهيز الرسالة الحالية
        current_message_content = user_input
        if file_content:
            current_message_content += f"\n\n[Attached File: {file_name}]\n{file_content}\n[End of File]"

        intent = resolve_intent(user_input)

        # ==========================================
        # 🎨 مسار الصور (Flux)
        # ==========================================
        if intent == "IMAGE":
            # 1. ترجمة الوصف (Gemini يترجم فقط الرسالة الحالية وليس التاريخ كله)
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 99999999)
            
            image_url = (
                f"{IMAGE_BASE_URL}/{encoded_prompt}"
                f"?model={MODEL_IMAGE}&width=1024&height=1024&seed={seed}&nologo=true"
            )
            
            html_response = (
                f"🎨 <b>Genisi Art:</b> {user_input}<br>"
                f"<small style='color:#888'>Translated: {english_prompt}</small><br>"
                f"<img src='{image_url}' alt='Generating...' style='width:100%; border-radius:10px; margin-top:10px;'>"
            )
            
            # نعيد نصاً بسيطاً ليحفظ في الذاكرة بدلاً من كود HTML الطويل
            memory_text = f"قمت بتوليد صورة بناءً على طلبك: {user_input}"
            
            return jsonify({"reply": html_response, "memory_text": memory_text})

        # ==========================================
        # 💻 مسار النصوص والذاكرة (Gemini)
        # ==========================================
        else:
            # بناء القائمة الكاملة للرسائل
            messages_payload = [
                {
                    "role": "system", 
                    "content": "You are Genisi, an expert AI assistant powered by Gemini. You are excellent at coding, debugging, and conversation. You have memory of the previous conversation."
                }
            ]
            
            # إضافة التاريخ السابق (Context)
            for msg in history:
                # التأكد من صحة الحقول لتجنب الأخطاء
                if 'role' in msg and 'content' in msg:
                    messages_payload.append(msg)

            # إضافة الرسالة الجديدة
            messages_payload.append({"role": "user", "content": current_message_content})

            payload = {
                "model": MODEL_TEXT,
                "messages": messages_payload,
                "temperature": 0.7,
                "stream": False
            }

            response = requests.post(TEXT_API_URL, json=payload, timeout=60)

            if response.status_code == 200:
                bot_reply = response.text
                # تنظيف الرد إذا كان JSON خام
                if bot_reply.strip().startswith('{') and '"content":' in bot_reply:
                     try:
                         json_data = json.loads(bot_reply)
                         if 'choices' in json_data:
                             bot_reply = json_data['choices'][0]['message']['content']
                     except:
                         pass

                display_reply = f"`[💎 Gemini]`\n\n{bot_reply}"
                # نعيد الرد للعرض، والرد للحفظ في الذاكرة
                return jsonify({"reply": display_reply, "memory_text": bot_reply})
            
            else:
                return jsonify({"reply": f"Error: {response.status_code}"}), 500

    except Exception as e:
        logger.error(f"Fatal Error: {e}")
        traceback.print_exc()
        return jsonify({"reply": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
