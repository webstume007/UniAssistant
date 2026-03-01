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
MOHSIN_PHONE = "923053296062@c.us" # Your official number

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

last_reply_time = 0

# --- 2. DATA FUNCTIONS (KEPT & UPDATED) ---

def save_to_db(info_text, msg_id=None):
    """Saves text or File IDs to Supabase (Unchanged logic)."""
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
    """Pulls facts and labels files clearly for the AI (Updated for better PDF recognition)."""
    try:
        data = supabase.table("knowledge").select("info", "message_id").execute()
        history = []
        for row in data.data:
            if row.get('message_id'):
                # Labeling files clearly so AI can match them to user requests
                history.append(f"Available File: '{row['info']}' (ForwardID: {row['message_id']})")
            else:
                history.append(f"Fact: {row['info']}")
        return "\n".join(history)
    except: return ""

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage/{API_TOKEN}", json={"chatId": chat_id, "message": text})

def forward_file(chat_id, message_id):
    """Native Forwarding (The API you shared)."""
    url = f"{BASE_URL}/forwardMessages/{API_TOKEN}"
    payload = {"chatId": chat_id, "messages": [message_id]}
    requests.post(url, json=payload)

# --- 3. MAIN LOGIC (PREVIOUS LOGIC PRESERVED + UPDATED) ---

def receive_and_process():
    global last_reply_time
    response = requests.get(f"{BASE_URL}/receiveNotification/{API_TOKEN}")
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # 🔥 ANTI-BURST: DELETE IMMEDIATELY
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
        
        if sender_id == BOT_PHONE: return

        message_data = body.get("messageData", {})
        msg_id_received = body.get("idMessage")
        type_msg = message_data.get("typeMessage")
        
        # Extract Text/Caption (Updated to ensure captions on PDFs are caught)
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "") or \
                    message_data.get("documentMessageData", {}).get("caption", "") or ""

        # --- A. TEACHING MODE (MOHSIN ONLY) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            
            # --- HANDLE PDF (UPDATED FOR BETTER NAMING) ---
            if type_msg == "documentMessage":
                doc_info = message_data.get("documentMessageData", {})
                # Logic: Use the caption you wrote, or the actual file name
                f_name = user_text if user_text else doc_info.get("fileName", "Class Document")
                
                if save_to_db(f_name, msg_id=msg_id_received):
                    send_message(sender_id, f"✅ Indexed PDF as: {f_name}")
                return

            # --- HANDLE TEXT UPDATE (AUTO-ORGANIZER KEPT) ---
            if user_text and "✅" not in user_text:
                res = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"Briefly structure this class update: {user_text}"}],
                    model="llama-3.3-70b-versatile",
                )
                fact = res.choices[0].message.content
                if save_to_db(fact):
                    send_message(sender_id, f"✅ Saved Fact: {fact}")
            return

        # --- B. ASSISTANT MODE (GROUP/@CR - PREVIOUS LOGIC KEPT) ---
        if "@cr" in user_text.lower():
            # ANTI-SPAM COOLDOWN
            if time.time() - last_reply_time < 8: return

            # HUMAN-LIKE DELAY & PRESENCE
            requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": sender_id, "presence": "composing"})
            time.sleep(random.uniform(4, 7))

            context = get_combined_knowledge()
            prompt = f"""
            You are the IUB Assistant. 
            Context: {context}
            User Question: {user_text}
            
            RULES:
            1. If the user asks for a file that exists in Context, reply ONLY with 'FWD:' + the ForwardID.
            2. If you don't have the file, say 'I don't have that file in my records.'
            3. Stay under 20 words. No @ tags.
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
            except Exception as e: print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Full Update) is starting...")
    while True:
        try: receive_and_process()
        except Exception as e: print(f"⚠️ Loop Error: {e}")
        time.sleep(2.5)
