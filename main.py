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

BOT_PHONE = "923468415931@c.us" 
MOHSIN_PHONE = "923053296062@c.us" # <-- YOUR NUMBER

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

last_reply_time = 0

# --- 2. FILE & KNOWLEDGE FUNCTIONS ---

def handle_file_upload(body):
    """Detects if Mohsin sent a file and saves its details."""
    message_data = body.get("messageData", {})
    file_type = None
    file_info = {}

    if "documentMessageData" in message_data:
        file_type = "Document"
        file_info = message_data["documentMessageData"]
    elif "imageMessageData" in message_data:
        file_type = "Image"
        file_info = message_data["imageMessageData"]
    
    if file_type:
        f_name = file_info.get("fileName", f"File_{int(time.time())}")
        f_url = file_info.get("downloadUrl")
        # Save to Supabase as a factual record
        fact = f"{file_type} Available: The file '{f_name}' can be found here: {f_url}"
        supabase.table("knowledge").insert({"info": fact}).execute()
        return f_name
    return None

def organize_and_save(raw_text):
    """Organizes text updates from Mohsin."""
    try:
        if "✅" in raw_text: return None
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": f"Organize this university fact: {raw_text}"}],
            model="llama-3.3-70b-versatile",
        )
        fact = response.choices[0].message.content
        supabase.table("knowledge").insert({"info": fact}).execute()
        return fact
    except: return None

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
    requests.post(f"{BASE_URL}/sendMessage/{API_TOKEN}", json={"chatId": chat_id, "message": text})

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

        # 1. DELETE NOTIFICATION IMMEDIATELY (Anti-Burst)
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

        # 2. BOT IDENTITY CHECK
        if sender_id == BOT_PHONE: return

        # 3. MESSAGE EXTRACTION
        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        # --- A. TEACHING MODE (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            # Check for Files first
            file_name = handle_file_upload(body)
            if file_name:
                send_message(sender_id, f"✅ File '{file_name}' added to memory.")
                return
            
            # If no file, treat as Text Update
            if user_text:
                fact = organize_and_save(user_text)
                if fact: send_message(sender_id, f"✅ Saved: {fact}")
            return

        # --- B. ASSISTANT MODE (GROUP) ---
        if "@cr" in user_text.lower():
            # Anti-Spam Cooldown (5 seconds)
            if time.time() - last_reply_time < 5: return

            # Show "typing..."
            requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": sender_id, "presence": "composing"})
            time.sleep(random.uniform(3, 6))

            context = get_combined_knowledge()
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": f"Context: {context}. Rule: If asked for a file/link, give the full URL. Max 25 words. No @ tags."},
                        {"role": "user", "content": user_text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                answer = chat_completion.choices[0].message.content
                send_message(sender_id, answer.replace("@", ""))
                last_reply_time = time.time()
            except Exception as e: print(f"⚠️ AI Error: {e}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (File & Cloud Mode) Online.")
    while True:
        try: receive_and_process()
        except Exception as e: print(f"⚠️ System Error: {e}")
        time.sleep(2)
