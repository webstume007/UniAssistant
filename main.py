import os
import time
import requests
from groq import Groq

# 1. Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") # Add this to Railway Variables
BOT_PHONE = "923468415931" 

# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "IUB AI Assistant for Semester 3. Developer: Mohsin Akhtar (Roll 1118)."

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

def receive_and_process():
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # ANTI-LOOP: Don't process messages from the bot itself
        if BOT_PHONE in sender_id:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        # TRIGGER: Listen specifically for @CR
        if user_text and "@cr" in user_text.lower():
            print(f"📩 Groq Processing @CR request from {sender_id}...")
            context = get_knowledge()
            
            try:
                # 2. CALL GROQ AI
                # Model 'llama-3.3-70b-versatile' is fast and very smart.
                chat_completion = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a helpful IUB University Assistant. Context: {context}. Rule: Only answer class topics. For others, say 'Ask Mohsin'."
                        },
                        {
                            "role": "user",
                            "content": user_text,
                        }
                    ],
                    model="llama-3.3-70b-versatile",
                )
                
                answer = chat_completion.choices[0].message.content
                if answer:
                    send_message(sender_id, answer)
                    print("📤 Groq Reply Sent!")

            except Exception as e:
                print(f"⚠️ Groq Error: {e}")
                if "429" in str(e):
                    # Rate limit fallback to a smaller, faster model
                    print("🔄 Rate limit hit, trying Llama 3.1 8B...")
                    # Add secondary logic here if needed

        # Always delete the notification
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (GROQ MODE) is starting...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1)
