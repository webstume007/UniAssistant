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
        return "I am the IUB AI Assistant. Developed by Mohsin Akhtar."

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

def receive_and_process():
    # Check for new messages
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        
        # Get Chat ID and Text
        chat_id = body.get("senderData", {}).get("chatId")
        message_data = body.get("messageData", {})
        
        user_text = ""
        # Finding the text in different possible formats
        if "textMessageData" in message_data:
            user_text = message_data["textMessageData"].get("textMessage", "")
        elif "extendedTextMessageData" in message_data:
            user_text = message_data["extendedTextMessageData"].get("text", "")

        if user_text:
            print(f"📩 New Message from {chat_id}: {user_text}")

            # Respond if 'bot' or '@bot' is mentioned
            if "bot" in user_text.lower():
                print("🧠 AI is thinking...")
                context = get_knowledge()
                ai_response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=f"Context: {context}\n\nStudent asked: {user_text}"
                )
                send_message(chat_id, ai_response.text)
                print("📤 Reply sent!")

        # CRITICAL: Delete notification so it doesn't loop
        delete_url = f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}"
        requests.delete(delete_url)

if __name__ == "__main__":
    print("🚀 IUB Assistant (Direct Mode) is starting...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ Error: {e}")
        time.sleep(2) # Checks every 2 seconds
