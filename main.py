import os
import time
import requests
from google import genai

# 1. Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_PHONE = "923468415931" 

client = genai.Client(api_key=GEMINI_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "IUB AI Assistant for Semester 3. Boss: Mohsin Akhtar."

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
        
        # ANTI-LOOP: If bot sends a msg containing @cr, skip it
        if BOT_PHONE in sender_id:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = ""
        if "textMessageData" in message_data:
            user_text = message_data["textMessageData"].get("textMessage", "")
        elif "extendedTextMessageData" in message_data:
            user_text = message_data["extendedTextMessageData"].get("text", "")

        # TRIGGER: Only @CR and Class Topics
        if user_text and "@cr" in user_text.lower():
            print(f"📩 @CR Request: {user_text}")
            
            context = get_knowledge()
            # Strict Instruction to prevent random chat
            system_msg = f"You are a strict University Assistant. Context: {context}. Rule: If the question isn't about the context, say 'Ask Mohsin'. Answer shortly."

            try:
                # 2026 BEST STABLE FREE MODEL
                response = client.models.generate_content(
                    model="gemini-2.0-flash-lite", 
                    contents=f"{system_msg}\n\nQuestion: {user_text}"
                )
                
                if response.text:
                    send_message(sender_id, response.text)
                    print("📤 Replied!")

            except Exception as e:
                print(f"⚠️ AI Error: {e}")
                if "429" in str(e):
                    send_message(sender_id, "Rate limit hit. Try in 30 seconds.")

        # Always delete notification
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Lite Mode) Started...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5)
