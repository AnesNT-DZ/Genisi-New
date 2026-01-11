from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import random
import urllib.parse
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- إعدادات Genisi ---
API_KEY = "sk_JHTVJDFsV7uiHdMVFqNKwzY8DZkhw0Oz" # مفتاحك
BASE_URL = "https://gen.pollinations.ai"

# --- النماذج ---
MODEL_CHAT_FAST = "openai"
MODEL_CHAT_CODE = "qwen-coder"

# نستخدم flux لأنه الأقوى حالياً وغالباً يعمل بالمجان
MODEL_IMAGE_DEFAULT = "flux" 
# نحاول استخدام seedance للفيديو، وإذا فشل سنحول للصورة
MODEL_VIDEO_DEFAULT = "seedance" 

def get_auth_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

def resolve_model(text, has_file, user_mode):
    """تحديد النية"""
    text_lower = text.lower()
    
    # 1. الفيديو
    video_keywords = ["video", "gif", "movie", "فيديو", "جيف", "متحركة", "مقطع"]
    if user_mode == "veo" or any(k in text_lower for k in video_keywords):
        return "VIDEO", MODEL_VIDEO_DEFAULT

    # 2. الصور
    image_keywords = ["ارسم", "صورة", "تخيل", "draw", "image", "paint"]
    if any(k in text_lower for k in image_keywords):
        return "IMAGE", MODEL_IMAGE_DEFAULT

    # 3. النصوص
    if user_mode == "openai": return "TEXT", MODEL_CHAT_FAST
    if user_mode == "qwen-coder": return "TEXT", MODEL_CHAT_CODE
    
    code_keywords = ["code", "python", "error", "api", "كود", "برمجة"]
    if has_file or any(k in text_lower for k in code_keywords):
        return "TEXT", MODEL_CHAT_CODE
    
    return "TEXT", MODEL_CHAT_FAST

def translate_prompt(text):
    try:
        payload = {
            "model": MODEL_CHAT_FAST,
            "messages": [
                {"role": "system", "content": "Translate to English for visual prompt. Output ONLY translation."},
                {"role": "user", "content": text}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions", 
            headers=get_auth_headers(), 
            json=payload, timeout=5
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except:
        pass
    return text

def check_url_status(url):
    """دالة خفيفة للتحقق مما إذا كان الرابط يعمل أم يعطي 403"""
    try:
        # نستخدم stream=True لقراءة الهيدر فقط دون تحميل الفيديو كاملاً
        # هذا يوفر الوقت ويمنع تعليق السيرفر
        r = requests.get(url, stream=True, timeout=5)
        if r.status_code == 403:
            return False # رصيد غير كافٍ
        return True # الرابط يعمل
    except:
        return True # نفترض أنه يعمل إذا حدث timeout

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
            full_context += f"\n\nFile: {file_name}\n{file_content}"

        intent, selected_model = resolve_model(user_input, bool(file_content), user_mode)

        # ---------------------------------------------
        # 🎥 معالجة الفيديو مع نظام الحماية (Fallback)
        # ---------------------------------------------
        if intent == "VIDEO":
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 999999)
            
            # محاولة بناء رابط الفيديو
            video_url = (
                f"{BASE_URL}/image/{encoded_prompt}"
                f"?model={MODEL_VIDEO_DEFAULT}"
                f"&seed={seed}&width=1024&height=576&aspectRatio=16:9&key={API_KEY}"
            )
            
            # التحقق هل لدينا رصيد؟
            is_valid = check_url_status(video_url)

            if is_valid:
                # الرصيد موجود، نعرض الفيديو
                html_response = (
                    f"🎥 <b>Genisi Video:</b> {user_input}<br>"
                    f"<small style='color:#888'>{english_prompt}</small><br>"
                    f"<video src='{video_url}' autoplay loop muted playsinline controls "
                    f"style='width:100%; border-radius:10px; margin-top:10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);'></video>"
                )
                return jsonify({"reply": html_response})
            else:
                # ⚠️ الرصيد نفد! نحول فوراً إلى صورة بدلاً من الخطأ
                logger.warning("Video 403 Forbidden (No Credits). Falling back to Image.")
                image_url = (
                    f"{BASE_URL}/image/{encoded_prompt}"
                    f"?model={MODEL_IMAGE_DEFAULT}" # استخدام flux المجاني
                    f"&width=1024&height=576&seed={seed}&nologo=true&key={API_KEY}"
                )
                html_response = (
                    f"⚠️ <b>تنبيه:</b> رصيد الفيديو غير كافٍ، قمت بتوليد صورة عالية الجودة بدلاً منه:<br>"
                    f"🎨 <b>Genisi Flux Art:</b> {user_input}<br>"
                    f"<img src='{image_url}' alt='Fallback Image' style='width:100%; border-radius:10px; margin-top:10px;'>"
                )
                return jsonify({"reply": html_response})

        # ---------------------------------------------
        # 🎨 معالجة الصور
        # ---------------------------------------------
        elif intent == "IMAGE":
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 999999)
            
            image_url = (
                f"{BASE_URL}/image/{encoded_prompt}"
                f"?model={MODEL_IMAGE_DEFAULT}"
                f"&width=1024&height=1024&seed={seed}&nologo=true&key={API_KEY}"
            )
            html_response = (
                f"🎨 <b>Genisi Flux:</b> {user_input}<br>"
                f"<small style='color:#888'>{english_prompt}</small><br>"
                f"<img src='{image_url}' alt='Genisi Image' style='width:100%; border-radius:10px; margin-top:10px;'>"
            )
            return jsonify({"reply": html_response})

        # ---------------------------------------------
        # 💬 معالجة النصوص
        # ---------------------------------------------
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

            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=get_auth_headers(),
                json=payload, timeout=60
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    bot_reply = data['choices'][0]['message']['content']
                except:
                    bot_reply = response.text
                
                badge = "⚡ GPT-4o" if selected_model == MODEL_CHAT_FAST else "💻 Qwen-Coder"
                bot_reply = f"`[{badge}]`\n\n{bot_reply}"
                return jsonify({"reply": bot_reply})
            
            return jsonify({"reply": f"Error: {response.status_code}"}), 500

    except Exception as e:
        logger.error(f"Fatal Error: {e}")
        traceback.print_exc()
        return jsonify({"reply": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
