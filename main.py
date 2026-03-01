import os
import time
import requests
from groq import Groq

# 1. Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
BOT_PHONE = "923468415931" 

# SAFETY CHECK: If the key is missing, don't crash, just wait.
if not GROQ_API_KEY:
    print("❌ ERROR: GROQ_API_KEY is not set in Railway Variables!")
    time.sleep(60) # Give you time to read the log
    exit(1)

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
        
        # ANTI-LOOP
        if BOT_PHONE in sender_id:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        # TRIGGER
        if user_text and "@cr" in user_text.lower():
            print(f"📩 Groq Processing @CR request...")
            context = get_knowledge()
            
            try:
                # Use llama-3.3-70b-versatile for high quality
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": f"You are IUB AI Assistant. Context: {context}. Only answer class topics."},
                        {"role": "user", "content": user_text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                
                answer = chat_completion.choices[0].message.content
                send_message(sender_id, answer)
                print("📤 Groq Reply Sent!")

            except Exception as e:
                print(f"⚠️ Groq Error: {e}")

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
