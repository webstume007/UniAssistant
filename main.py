import os
import time
import requests
from google import genai

# 1. Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_PHONE = "923468415931"  # <--- UPDATE THIS TO YOUR BOT'S NUMBER

client = genai.Client(api_key=GEMINI_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

# Simple Memory Storage (Last 5 messages per chat)
chat_memory = {}

def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "I am the IUB AI Assistant for 3rd Semester. My boss is Mohsin Akhtar."

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
        
        # 2. ANTI-LOOP: Check sender
        sender_data = body.get("senderData", {})
        sender_id = sender_data.get("chatId", "") # Looks like 923xx@c.us
        chat_id = sender_id # The group or private chat ID
        
        # If the message is from the bot itself, delete and skip
        if BOT_PHONE in sender_id:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = ""
        if "textMessageData" in message_data:
            user_text = message_data["textMessageData"].get("textMessage", "")
        elif "extendedTextMessageData" in message_data:
            user_text = message_data["extendedTextMessageData"].get("text", "")

        if user_text and "@cr" in user_text.lower():
            print(f"📩 Processing @CR request from {sender_id}...")
            
            # 3. MEMORY LOGIC: Get previous context
            if chat_id not in chat_memory:
                chat_memory[chat_id] = []
            
            history = "\n".join(chat_memory[chat_id])
            context = get_knowledge()
            
            # 4. SYSTEM INSTRUCTION (The Class-Only Filter)
            system_prompt = f"""
            SYSTEM: You are the IUB AI Assistant. 
            RULES: 
            1. ONLY answer questions about IUB, AI Dept, Semester 3, and Class tasks.
            2. If the user asks about unrelated topics (politics, sports, general chat), politely say: 'I only handle IUB Class matters. Ask Mohsin for other things.'
            3. Use the following Knowledge Base: {context}
            4. Previous conversation: {history}
            """

            try:
                ai_response = client.models.generate_content(
                    model="gemini-2.0-flash", # Use 2.0 or 1.5 based on what worked last
                    contents=f"{system_prompt}\n\nStudent: {user_text}"
                )
                
                if ai_response.text:
                    send_message(chat_id, ai_response.text)
                    # Update memory (keep last 5)
                    chat_memory[chat_id].append(f"Student: {user_text}")
                    chat_memory[chat_id].append(f"Bot: {ai_response.text}")
                    chat_memory[chat_id] = chat_memory[chat_id][-10:] # 5 pairs
                    print("📤 Reply sent!")
            except Exception as e:
                print(f"⚠️ AI Error: {e}")

        # Always delete the notification
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Memory & Anti-Loop) Started...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ Error: {e}")
        time.sleep(1)
