import os
import time
import requests
from google import genai

# 1. Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

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
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        
        chat_id = body.get("senderData", {}).get("chatId")
        message_data = body.get("messageData", {})
        
        user_text = ""
        if "textMessageData" in message_data:
            user_text = message_data["textMessageData"].get("textMessage", "")
        elif "extendedTextMessageData" in message_data:
            user_text = message_data["extendedTextMessageData"].get("text", "")

        if user_text:
            # 2. TRIGGER: Only respond if '@cr' is mentioned
            if "@cr" in user_text.lower():
                print(f"📩 @CR mentioned. Processing for {chat_id}...")
                context = get_knowledge()
                
                try:
                    # 3. MODEL: Using 1.5-flash for a stable free quota
                    response = client.models.generate_content(
                        model="gemini-1.5-flash", 
                        contents=f"Context: {context}\n\nQuestion: {user_text}"
                    )
                    
                    if response.text:
                        send_message(chat_id, response.text)
                        print("📤 Reply sent!")
                except Exception as ai_err:
                    print(f"⚠️ Gemini Quota Error: {ai_err}")
                    # Only notify the user if it's a real quota issue
                    if "429" in str(ai_err):
                        send_message(chat_id, "Too many requests. Please wait a minute before asking @CR again.")

        # Always delete the notification so we don't process it again
        delete_url = f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}"
        requests.delete(delete_url)

if __name__ == "__main__":
    print("🚀 IUB Assistant Active. Only listening for @CR...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5) # Small delay to be safe
