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
API_KEY = "sk_JHTVJDFsV7uiHdMVFqNKwzY8DZkhw0Oz"
BASE_URL = "https://gen.pollinations.ai"

# --- النماذج ---
MODEL_CHAT_FAST = "openai"
MODEL_CHAT_CODE = "qwen-coder"
MODEL_IMAGE = "nanobanana-pro"
MODEL_VIDEO = "veo"  # نموذج الفيديو الجديد

def get_auth_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

def resolve_model(text, has_file, user_mode):
    """تحديد النية بناءً على اختيار المستخدم ومحتوى الرسالة"""
    text_lower = text.lower()
    
    # 1. الاختيار اليدوي الصريح من القائمة
    if user_mode == "veo":
        return "VIDEO", MODEL_VIDEO
    if user_mode == "openai":
        return "TEXT", MODEL_CHAT_FAST
    if user_mode == "qwen-coder":
        return "TEXT", MODEL_CHAT_CODE
    
    # 2. الوضع التلقائي (Auto)
    
    # هل يطلب فيديو؟
    video_keywords = ["video", "movie", "clip", "فيديو", "مقطع", "فيلم", "تحريك"]
    if any(k in text_lower for k in video_keywords):
        return "VIDEO", MODEL_VIDEO

    # هل يطلب صورة؟
    image_keywords = ["ارسم", "صورة", "تخيل", "draw", "generate image", "paint"]
    if any(k in text_lower for k in image_keywords):
        return "IMAGE", MODEL_IMAGE

    # هل يطلب كود أو يوجد ملف؟
    code_keywords = ["code", "python", "java", "html", "error", "debug", "api", "كود", "برمجة"]
    if has_file or any(k in text_lower for k in code_keywords):
        return "TEXT", MODEL_CHAT_CODE
    
    # الافتراضي
    return "TEXT", MODEL_CHAT_FAST

def translate_prompt(text):
    """ترجمة الوصف للإنجليزية (مهم جداً للصور والفيديو)"""
    try:
        payload = {
            "model": MODEL_CHAT_FAST,
            "messages": [
                {"role": "system", "content": "Translate to English description. Output ONLY translation."},
                {"role": "user", "content": text}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions", 
            headers=get_auth_headers(), 
            json=payload, timeout=10
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
            full_context += f"\n\nFile: {file_name}\n{file_content}"

        # تحديد النية
        intent, selected_model = resolve_model(user_input, bool(file_content), user_mode)

        # ---------------------------------------------
        # 🎥 معالجة الفيديو (Veo)
        # ---------------------------------------------
        if intent == "VIDEO":
            english_prompt = translate_prompt(user_input)
            encoded_prompt = urllib.parse.quote(english_prompt)
            seed = random.randint(0, 999999)
            
            # رابط الفيديو (يستخدم نفس endpoint الصور لكن مع model=veo)
            video_url = (
                f"{BASE_URL}/image/{encoded_prompt}"
                f"?model={MODEL_VIDEO}"
                f"&seed={seed}"
                f"&width=1024&height=576" # أبعاد سينمائية
                f"&aspectRatio=16:9"
                f"&key={API_KEY}"
            )
            
            html_response = (
                f"🎥 <b>Genisi Cinema (Veo):</b> {user_input}<br>"
                f"<small style='color:#888'>{english_prompt}</small><br>"
                f"<video controls autoplay loop src='{video_url}' style='width:100%; border-radius:10px; margin-top:10px; box-shadow:0 5px 20px rgba(0,0,0,0.5);'></video>"
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
                f"?model={MODEL_IMAGE}&width=1024&height=1024&seed={seed}&nologo=true&key={API_KEY}"
            )
            html_response = (
                f"🎨 <b>Genisi Art:</b> {user_input}<br>"
                f"<small style='color:#888'>{english_prompt}</small><br>"
                f"<img src='{image_url}' alt='Generating...' style='width:100%; border-radius:10px; margin-top:10px;'>"
            )
            return jsonify({"reply": html_response})

        # ---------------------------------------------
        # 💬 معالجة النصوص/البرمجة
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
