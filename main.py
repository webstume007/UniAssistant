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

# 2. Memory Storage (Dictionary to store last 5 exchanges per chat)
chat_memory = {}

def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "IUB AI Assistant. Developed by Mohsin Akhtar."

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
        
        # Anti-Loop: Skip messages from the bot itself
        if BOT_PHONE in sender_id:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        # Trigger for @CR
        if user_text and "@cr" in user_text.lower():
            print(f"📩 Processing @CR request from {sender_id}...")
            
            # 3. Handle Memory
            if sender_id not in chat_memory:
                chat_memory[sender_id] = []
            
            context = get_knowledge()
            
            # Build the message list for the AI
            messages = [
                {"role": "system", "content": f"You are the IUB AI Assistant. Knowledge: {context}. Rule: Be helpful, friendly, and keep responses under 25 words. Do NOT say 'class enquiries only'. Never use the word '@CR'."}
            ]
            
            # Add previous chat history to the prompt
            for hist in chat_memory[sender_id]:
                messages.append(hist)
            
            # Add current user message
            messages.append({"role": "user", "content": user_text})
            
            try:
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                )
                
                answer = chat_completion.choices[0].message.content
                clean_answer = answer.replace("@", "") # Safety check for tags
                
                if clean_answer:
                    send_message(sender_id, clean_answer)
                    
                    # Update memory (Save user msg and bot response)
                    chat_memory[sender_id].append({"role": "user", "content": user_text})
                    chat_memory[sender_id].append({"role": "assistant", "content": clean_answer})
                    
                    # Keep only the last 10 messages (5 pairs) to save memory/speed
                    chat_memory[sender_id] = chat_memory[sender_id][-10:]
                    print("📤 Smart Reply Sent!")

            except Exception as e:
                print(f"⚠️ Groq Error: {e}")

        # Always delete the notification
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (With Memory) is starting...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5)
