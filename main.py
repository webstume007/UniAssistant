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
MOHSIN_PHONE = "923053296062@c.us" 

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

last_reply_time = 0

# --- 2. DATABASE UTILITIES ---

def save_to_db(info_text, msg_id=None):
    try:
        data = {"info": str(info_text)}
        if msg_id: data["message_id"] = str(msg_id)
        supabase.table("knowledge").insert(data).execute()
        return True
    except Exception as e:
        print(f"❌ Knowledge DB Error: {e}")
        return False

def get_combined_knowledge():
    try:
        data = supabase.table("knowledge").select("info", "message_id").execute()
        lines = []
        for r in data.data:
            if r.get('message_id'):
                lines.append(f"DATABASE_FILE: Name='{r['info']}', ID='{r['message_id']}'")
            else:
                lines.append(f"CLASS_FACT: {r['info']}")
        return "\n".join(lines) if lines else "No class data available."
    except: return "Database connection error."

def save_chat_history(user_id, message, role):
    try:
        supabase.table("chat_history").insert({
            "user_id": str(user_id), "message": str(message), "role": str(role)
        }).execute()
    except: pass

def get_chat_history(user_id, limit=5):
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
    url = f"{BASE_URL}/forwardMessages/{API_TOKEN}"
    payload = {"chatId": chat_id, "messages": [message_id]}
    res = requests.post(url, json=payload)
    print(f"🚀 Forwarding Attempt: {res.status_code}")

# --- 4. MAIN PROCESSOR ---

def receive_and_process():
    global last_reply_time
    response = requests.get(f"{BASE_URL}/receiveNotification/{API_TOKEN}")
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        if not receipt_id or sender_id == BOT_PHONE:
            if receipt_id: requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        msg_id_received = body.get("idMessage")
        type_msg = message_data.get("typeMessage")
        
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "") or \
                    message_data.get("documentMessageData", {}).get("caption", "") or ""

        # --- A. TEACHING MODE (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            if type_msg == "documentMessage":
                f_name = message_data.get("documentMessageData", {}).get("fileName") or user_text or "PDF"
                if save_to_db(f_name, msg_id=msg_id_received):
                    send_message(sender_id, f"✅ PDF '{f_name}' indexed for class access.")
            
            elif user_text and "✅" not in user_text:
                res = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"You are Mohsin's Personal Organizer. Structure this class update for the database: {user_text}"}],
                    model="llama-3.3-70b-versatile",
                )
                fact = res.choices[0].message.content
                if save_to_db(fact):
                    send_message(sender_id, f"✅ Organized & Saved: {fact}")
            
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        # --- B. ASSISTANT MODE (GROUP/@CR) ---
        if "@cr" in user_text.lower():
            if time.time() - last_reply_time < 6:
                requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
                return

            set_typing_status(sender_id)
            time.sleep(random.uniform(3, 5))

            kb_context = get_combined_knowledge()
            chat_mem = get_chat_history(sender_id)
            
            # THE CORE INSTRUCTIONS (DO NOT MODIFY)
            system_instructions = f"""
            Persona: You are the 'Mohsins Personal Assistant', a bot for reducing burdon of BOSS Mohsin and helping class students at IUB. 
            Tone: Professional, helpful, and concise.
            Database Content: {kb_context}
            
            Rules:
            - Primirly you are desinged to answer question about Class and study by data provided in database by CR.
            - Try to answer minimal but also can reply long if needed.
            1. Any Question about class or study about that you dont know reply "I dont know about this Let me ask my BOSS Mohsin :)"
            2. If you don't know the answer, use your memory of previous chats to help, or say you don't have that info yet.
            """

            messages = [{"role": "system", "content": system_instructions}]
            for m in chat_mem: messages.append(m)
            messages.append({"role": "user", "content": user_text})

            try:
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                )
                answer = chat_completion.choices[0].message.content
                
                # Save Interaction to Memory
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

        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Master Script) Online.")
    while True:
        try: receive_and_process()
        except: pass
        time.sleep(2)
