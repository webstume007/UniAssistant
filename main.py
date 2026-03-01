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
        return "IUB AI Assistant. Boss: Mohsin Akhtar (Roll 1118)."

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

def get_ai_response(prompt):
    # Try the Primary 2026 Stable Model first
    models_to_try = ["gemini-2.0-flash-lite", "gemini-1.5-flash-8b"]
    
    for model_name in models_to_try:
        try:
            print(f"🧠 Attempting AI with: {model_name}...")
            response = client.models.generate_content(
                model=model_name, 
                contents=prompt
            )
            if response.text:
                return response.text
        except Exception as e:
            print(f"⚠️ {model_name} failed: {e}")
            continue # Move to the backup model
            
    return "AI is currently unavailable. Ask Mohsin directly."

def receive_and_process():
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # ANTI-LOOP: If the bot is the sender, skip
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
            print(f"📩 Valid @CR request received.")
            
            context = get_knowledge()
            system_instruction = f"Context: {context}. Rule: Only answer class-related info. Else, say 'Ask Mohsin'."
            
            answer = get_ai_response(f"{system_instruction}\n\nQuestion: {user_text}")
            if answer:
                send_message(sender_id, answer)
                print("📤 Replied successfully!")

        # Always delete notification
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Failover Mode) Started...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5)
