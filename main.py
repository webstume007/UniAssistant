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

chat_memory = {}
last_request_time = 0

def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "I am the IUB AI Assistant. Developed by Mohsin Akhtar (Roll 1118)."

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

def receive_and_process():
    global last_request_time
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # ANTI-LOOP: Don't reply to yourself
        if BOT_PHONE in sender_id:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = ""
        if "textMessageData" in message_data:
            user_text = message_data["textMessageData"].get("textMessage", "")
        elif "extendedTextMessageData" in message_data:
            user_text = message_data["extendedTextMessageData"].get("text", "")

        # Only trigger for @CR and ignore everything else
        if user_text and "@cr" in user_text.lower():
            
            # Rate limiting check: Don't allow requests faster than every 4 seconds
            current_time = time.time()
            if current_time - last_request_time < 4:
                print("⏳ Throttling: Request too fast.")
                requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
                return

            print(f"📩 Processing @CR request from {sender_id}...")
            context = get_knowledge()
            
            # Simplified prompt to save tokens
            system_instruction = f"You are IUB AI Assistant. Only answer class-related questions based on this: {context}. Otherwise, tell them to ask Mohsin."

            try:
                # SWITCHED TO 1.5-FLASH FOR BETTER FREE QUOTA
                ai_response = client.models.generate_content(
                    model="gemini-1.5-flash", 
                    contents=f"{system_instruction}\n\nUser: {user_text}"
                )
                
                if ai_response.text:
                    send_message(sender_id, ai_response.text)
                    last_request_time = time.time()
                    print("📤 Reply sent!")
                    
            except Exception as e:
                if "429" in str(e):
                    print("⚠️ QUOTA EXHAUSTED. Sleeping for 30s...")
                    send_message(sender_id, "🚫 Bot is tired (Google Limit). Try again in 1 minute.")
                    time.sleep(30) # Force a pause
                else:
                    print(f"⚠️ Error: {e}")

        # Always delete the notification
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Stable Mode) Started...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5)
