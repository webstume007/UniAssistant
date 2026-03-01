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

# IDs must be in format "923XXXXXXXXX@c.us"
BOT_PHONE = "923468415931@c.us" 
MOHSIN_PHONE = "923053296062@c.us" # <--- REPLACE WITH YOUR NUMBER

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

last_reply_time = 0

# --- 2. DATA FUNCTIONS ---

def save_to_db(info_text, msg_id=None):
    """Saves text or File IDs to Supabase."""
    try:
        data = {"info": info_text}
        if msg_id:
            data["message_id"] = msg_id
        supabase.table("knowledge").insert(data).execute()
        return True
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return False

def get_combined_knowledge():
    """Pulls all facts and file records from Supabase."""
    try:
        data = supabase.table("knowledge").select("info", "message_id").execute()
        # Combine everything into a readable context for Groq
        history = []
        for row in data.data:
            line = row['info']
            if row.get('message_id'):
                line += f" (ForwardID: {row['message_id']})"
            history.append(line)
        return " ".join(history)
    except: return ""

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage/{API_TOKEN}", json={"chatId": chat_id, "message": text})

def forward_file(chat_id, message_id):
    """Forwards a stored message ID to the user."""
    url = f"{BASE_URL}/forwardMessages/{API_TOKEN}"
    payload = {"chatId": chat_id, "messages": [message_id]}
    requests.post(url, json=payload)

# --- 3. MAIN LOGIC ---

def receive_and_process():
    global last_reply_time
    response = requests.get(f"{BASE_URL}/receiveNotification/{API_TOKEN}")
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # 🔥 CRITICAL: DELETE IMMEDIATELY TO STOP BURST/LOOPS
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
        
        if sender_id == BOT_PHONE: return

        message_data = body.get("messageData", {})
        msg_id_received = body.get("idMessage")
        
        # Detect Content Types
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "") or \
                    message_data.get("documentMessageData", {}).get("caption", "")
        
        is_file = "documentMessageData" in message_data or "imageMessageData" in message_data

        # --- A. TEACHING MODE (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            
            # Handle File Upload
            if is_file:
                f_name = message_data.get("documentMessageData", {}).get("fileName") or "File"
                if save_to_db(f"FILE_NAME: {f_name}", msg_id=msg_id_received):
                    send_message(sender_id, f"✅ Indexed File: {f_name}. Students can now ask for it.")
                return

            # Handle Text Update
            if user_text and "✅" not in user_text:
                res = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"Organize this class update: {user_text}"}],
                    model="llama-3.3-70b-versatile",
                )
                fact = res.choices[0].message.content
                if save_to_db(fact):
                    send_message(sender_id, f"✅ Organized & Saved: {fact}")
            return

        # --- B. ASSISTANT MODE (GROUP/@CR) ---
        if "@cr" in user_text.lower():
            # Cooldown to prevent spam
            if time.time() - last_reply_time < 8: return

            # Human Delay & Presence
            requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": sender_id, "presence": "composing"})
            time.sleep(random.uniform(4, 7))

            context = get_combined_knowledge()
            prompt = f"""
            Context: {context}
            User Question: {user_text}
            
            RULES:
            1. If user wants a file, reply ONLY with 'FWD:' followed by the ForwardID from context.
            2. Otherwise, reply naturally in <20 words.
            3. Do not use @ symbols.
            """

            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                )
                answer = chat_completion.choices[0].message.content

                if "FWD:" in answer:
                    target_id = answer.split("FWD:")[1].strip()
                    forward_file(sender_id, target_id)
                else:
                    send_message(sender_id, answer.replace("@", ""))
                
                last_reply_time = time.time()
                print("📤 Safe Reply Sent.")
            except Exception as e:
                print(f"⚠️ AI Error: {e}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Ultimate Mode) Online.")
    while True:
        try: receive_and_process()
        except: pass
        time.sleep(2.5)
