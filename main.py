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
MOHSIN_PHONE = "923053296062@c.us" # Your verified ID

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

last_reply_time = 0

# --- 2. DATA & MEMORY FUNCTIONS ---

def save_to_db(info_text, msg_id=None):
    """Saves static facts or File IDs to Supabase."""
    try:
        data = {"info": str(info_text)}
        if msg_id: data["message_id"] = str(msg_id)
        supabase.table("knowledge").insert(data).execute()
        return True
    except Exception as e:
        print(f"❌ Knowledge DB Error: {e}")
        return False

def get_combined_knowledge():
    """Pulls all facts and file records from Supabase."""
    try:
        data = supabase.table("knowledge").select("info", "message_id").execute()
        lines = []
        for r in data.data:
            if r.get('message_id'):
                lines.append(f"DATABASE_FILE: Name='{r['info']}', ID='{r['message_id']}'")
            else:
                lines.append(f"FACT: {r['info']}")
        return "\n".join(lines) if lines else "No class data yet."
    except: return "Database connection offline."

def save_chat_history(user_id, message, role):
    try:
        # We use str() to ensure it's not a dictionary or object
        clean_message = str(message) 
        supabase.table("chat_history").insert({
            "user_id": str(user_id), 
            "message": clean_message, 
            "role": str(role)
        }).execute()
        print(f"💾 Memory Saved: {role} -> {user_id}")
    except Exception as e:
        print(f"❌ Memory Save Error: {e}")

def get_chat_history(user_id, limit=50):
    """Retrieves the last few messages for a specific user."""
    try:
        data = supabase.table("chat_history").select("message", "role")\
            .eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        history = []
        for row in reversed(data.data):
            history.append({"role": row['role'], "content": row['message']})
        return history
    except: return []

# --- 3. WHATSAPP ACTIONS ---

def set_typing_status(chat_id):
    requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": chat_id, "presence": "composing"})

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage/{API_TOKEN}", json={"chatId": chat_id, "message": text})

def forward_file(chat_id, message_id):
    """Uses Native Forwarding API."""
    url = f"{BASE_URL}/forwardMessages/{API_TOKEN}"
    payload = {"chatId": chat_id, "messages": [message_id]}
    res = requests.post(url, json=payload)
    print(f"🚀 Forward Result: {res.status_code} for ID {message_id}")

# --- 4. MAIN ENGINE ---

def receive_and_process():
    global last_reply_time
    response = requests.get(f"{BASE_URL}/receiveNotification/{API_TOKEN}")
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # Identity Protection
        if not receipt_id or sender_id == BOT_PHONE:
            if receipt_id: requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        msg_id_received = body.get("idMessage")
        type_msg = message_data.get("typeMessage")
        
        # Extract Text/Caption
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "") or \
                    message_data.get("documentMessageData", {}).get("caption", "") or ""

        # --- MODE A: TEACHING (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            if type_msg == "documentMessage":
                f_name = message_data.get("documentMessageData", {}).get("fileName") or user_text or "PDF"
                if save_to_db(f_name, msg_id=msg_id_received):
                    send_message(sender_id, f"✅ PDF '{f_name}' Indexed for forwarding.")
            
            elif user_text and "✅" not in user_text:
                try:
                    res = client.chat.completions.create(
                        messages=[{"role": "user", "content": f"Structure this: {user_text}"}],
                        model="llama-3.3-70b-versatile",
                    )
                    fact = res.choices[0].message.content
                    if save_to_db(fact):
                        send_message(sender_id, f"✅ Saved: {fact}")
                except: pass
            
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        # --- MODE B: ASSISTANT (GROUP/@CR) ---
        if "@cr" in user_text.lower():
            # Anti-Spam Cooldown
            if time.time() - last_reply_time < 6:
                requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
                return

            set_typing_status(sender_id)
            time.sleep(random.uniform(3, 5))

            # Memory & Context
            kb_context = get_combined_knowledge()
            chat_mem = get_chat_history(sender_id)
            
            messages = [{"role": "system", "content": f"You are the IUB Assistant. Knowledge: {kb_context}. Rule: If file requested, reply ONLY 'FWD: [ID]'. Else, be brief."}]
            for m in chat_mem: messages.append(m)
            messages.append({"role": "user", "content": user_text})

            try:
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                )
                answer = chat_completion.choices[0].message.content
                
                # Save to Memory
                save_chat_history(sender_id, user_text, "user")
                save_chat_history(sender_id, answer, "assistant")

                if "FWD:" in answer:
                    target_id = answer.replace("FWD:", "").strip()
                    forward_file(sender_id, target_id)
                else:
                    send_message(sender_id, answer.replace("@", ""))
                
                last_reply_time = time.time()
            except Exception as e:
                print(f"⚠️ AI Error: {e}")

        # Final Cleanup
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Ultimate Memory Mode) starting...")
    while True:
        try: receive_and_process()
        except: pass
        time.sleep(2)
