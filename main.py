import os
import time
import random
import requests
from groq import Groq
from supabase import create_client

# --- 1. CONFIGURATION ---
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
SUPA_URL = os.environ.get("SUPABASE_URL")
SUPA_KEY = os.environ.get("SUPABASE_KEY")

# MAKE SURE THESE ARE 100% CORRECT
BOT_PHONE = "923468415931@c.us" 
MOHSIN_PHONE = "923XXXXXXXXX@c.us" # Replace with your personal number

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

last_reply_time = 0

# --- 2. THE ORGANIZER FUNCTION ---

def organize_and_save(raw_text):
    try:
        # Don't try to organize a message that is already a confirmation
        if "✅" in raw_text or "Organized & Saved" in raw_text:
            return None

        organizer_prompt = f"Convert this university update into a short factual sentence: {raw_text}"
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": organizer_prompt}],
            model="llama-3.3-70b-versatile",
        )
        organized_text = response.choices[0].message.content
        
        supabase.table("knowledge").insert({"info": organized_text}).execute()
        return organized_text
    except Exception as e:
        print(f"❌ Organizing Error: {e}")
        return None

def get_combined_knowledge():
    cloud_data = ""
    try:
        data = supabase.table("knowledge").select("info").execute()
        cloud_data = " ".join([row['info'] for row in data.data])
    except: pass
    
    local_data = ""
    try:
        if os.path.exists("knowledge_base.txt"):
            with open("knowledge_base.txt", "r") as f: local_data = f.read()
    except: pass
    return f"{local_data} {cloud_data}"

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

# --- 3. MAIN LOGIC ---

def receive_and_process():
    global last_reply_time
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")

        # 1. DELETE IMMEDIATELY
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

        # 2. STRICT SENDER FILTER (Stop the loop here)
        if sender_id == BOT_PHONE:
            return

        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        if not user_text: return

        # 3. CONTENT FILTER (If the text looks like the bot's own success message, skip)
        if "✅" in user_text or "Organized & Saved" in user_text:
            return

        # 4. COOLDOWN CHECK
        if time.time() - last_reply_time < 5: return

        # --- A. TEACHING MODE ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            fact = organize_and_save(user_text)
            if fact:
                send_message(sender_id, f"✅ Organized & Saved: {fact}")
                last_reply_time = time.time()
            return

        # --- B. ASSISTANT MODE ---
        if "@cr" in user_text.lower():
            # Show "typing..."
            requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": sender_id, "presence": "composing"})
            time.sleep(random.uniform(3, 5))

            context = get_combined_knowledge()
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": f"Context: {context}. Rule: Max 15 words. No @ tags."},
                        {"role": "user", "content": user_text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                answer = chat_completion.choices[0].message.content
                send_message(sender_id, answer.replace("@", ""))
                last_reply_time = time.time()
            except Exception as e:
                print(f"⚠️ AI Error: {e}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Anti-Loop Fixed) Online.")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(2)
