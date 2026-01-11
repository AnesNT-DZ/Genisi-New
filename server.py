from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)  # تفعيل CORS

# الرابط الرسمي حسب التوثيق (OpenAI-compatible endpoint)
POLLINATIONS_URL = "https://gen.pollinations.ai/v1/chat/completions"

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    # 1. إعداد الـ Headers كما هو مطلوب في التوثيق
    headers = {
        "Content-Type": "application/json",
        # إذا كان لديك مفتاح API ضعه هنا، وإذا لم يوجد اتركها، المنصة غالباً تعمل بدونه للاستخدام العادي
        # "Authorization": "Bearer YOUR_API_KEY" 
    }

    # 2. إعداد الـ Body (البيانات) حسب هيكلة OpenAI المذكورة في التوثيق
    payload = {
        "model": "openai", # الموديل الافتراضي حسب التوثيق
        "messages": [
            {
                "role": "system",
                "content": "أنت Genisi، مساعد ذكي ومحترف، تتحدث العربية بطلاقة."
            },
            {
                "role": "user",
                "content": user_input
            }
        ],
        "temperature": 0.7,
        "stream": False
    }

    try:
        # إرسال طلب POST
        response = requests.post(POLLINATIONS_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # 3. استخراج الرد حسب هيكلة JSON الموضحة في التوثيق
            # Structure: choices[0] -> message -> content
            bot_reply = data['choices'][0]['message']['content']
            return jsonify({"reply": bot_reply})
        else:
            print(f"Error {response.status_code}: {response.text}")
            return jsonify({"reply": f"عذراً، خطأ من المصدر: {response.status_code}"}), 500
            
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"reply": "حدث خطأ داخلي في الخادم."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
