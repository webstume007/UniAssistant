import os
import time
import requests
from groq import Groq

# 1. Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
BOT_PHONE = "923468415931" 

# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "IUB AI Assistant for Semester 3. Developer: Mohsin Akhtar."

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
        
        # --- LOOP KILLER (Inside the function now) ---
        if BOT_PHONE in sender_id:
            print("🚫 Message from myself. Deleting to avoid loop.")
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return # This is now valid because it's inside receive_and_process()

        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        # --- TRIGGER: Only @CR ---
        if user_text and "@cr" in user_text.lower():
            print(f"📩 Valid @CR request received.")
            context = get_knowledge()
            
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": f"""
                            You are the IUB AI Assistant. 
                            RULES:
                            1. NEVER use the word '@CR' or tag anyone in your response.
                            2. Keep answers shorter than 15 words.
                            3. Only discuss class topics from this context: {context}.
                            4. If the question is random, say: 'Class queries only.'
                            """
                        },
                        {"role": "user", "content": user_text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                
                answer = chat_completion.choices[0].message.content
                # Strip any accidental @ symbols
                clean_answer = answer.replace("@", "")
                
                if clean_answer:
                    send_message(sender_id, clean_answer)
                    print("📤 Cleaned Reply Sent!")

            except Exception as e:
                print(f"⚠️ Groq Error: {e}")

        # Always delete the notification at the end
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Fixed Syntax) is starting...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5)
