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
MOHSIN_PHONE = "923053296062@c.us" # <--- ENSURE THIS IS YOUR EXACT NUMBER

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
        type_msg = message_data.get("typeMessage")
        
        # Extract Text/Caption
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "") or \
                    message_data.get("documentMessageData", {}).get("caption", "") or \
                    message_data.get("imageMessageData", {}).get("caption", "") or ""

        # --- A. TEACHING MODE (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            
            # --- 📄 HANDLE PDF/DOCUMENTS ---
            if type_msg == "documentMessage":
                doc_info = message_data.get("documentMessageData", {})
                f_name = doc_info.get("fileName", "Class_File")
                if save_to_db(f"FILE_NAME: {f_name}", msg_id=msg_id_received):
                    send_message(sender_id, f"✅ PDF '{f_name}' saved. Students can ask for it via @CR.")
                return

            # --- 📸 HANDLE IMAGES ---
            if type_msg == "imageMessage":
                if save_to_db("IMAGE_FILE", msg_id=msg_id_received):
                    send_message(sender_id, "✅ Image saved and ready to forward.")
                return

            # --- ✍️ HANDLE TEXT UPDATE ---
            if user_text and "✅" not in user_text:
                res = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"Structure this class update: {user_text}"}],
                    model="llama-3.3-70b-versatile",
                )
                fact = res.choices[0].message.content
                if save_to_db(fact):
                    send_message(sender_id, f"✅ Saved: {fact}")
            return

        # --- B. ASSISTANT MODE (GROUP/@CR) ---
        if "@cr" in user_text.lower():
            if time.time() - last_reply_time < 8: return

            requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": sender_id, "presence": "composing"})
            time.sleep(random.uniform(4, 7))

            context = get_combined_knowledge()
            prompt = f"Context: {context}\nQuestion: {user_text}\nRule: If asking for file, reply ONLY with 'FWD:' + ForwardID. Else, be natural <20 words."

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
            except Exception as e: print(f"⚠️ AI Error: {e}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Full Hybrid Mode) is starting...")
    while True:
        try: receive_and_process()
        except Exception as e: print(f"⚠️ Error: {e}")
        time.sleep(2.5)
