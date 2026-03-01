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

# --- 2. DATA & UTILITY FUNCTIONS (ALL PREVIOUS LOGIC) ---

def save_to_db(info_text, msg_id=None):
    """Saves text or File IDs to Supabase."""
    try:
        data = {"info": str(info_text)}
        if msg_id:
            data["message_id"] = str(msg_id)
        supabase.table("knowledge").insert(data).execute()
        return True
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return False

def get_combined_knowledge():
    """Pulls facts and labels files clearly for the AI."""
    try:
        data = supabase.table("knowledge").select("info", "message_id").execute()
        history = []
        for row in data.data:
            if row.get('message_id'):
                # Labeling files clearly so AI can match them
                history.append(f"DATABASE_FILE: Name='{row['info']}', MessageID='{row['message_id']}'")
            else:
                history.append(f"FACT: {row['info']}")
        return "\n".join(history)
    except: return ""

def set_typing_status(chat_id):
    """Makes the bot look human by showing 'typing...'"""
    url = f"{BASE_URL}/setPresence/{API_TOKEN}"
    payload = {"chatId": chat_id, "presence": "composing"}
    requests.post(url, json=payload)

def send_message(chat_id, text):
    """Sends a standard text message."""
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

def forward_file(chat_id, message_id):
    """Native Forwarding via the API you shared."""
    url = f"{BASE_URL}/forwardMessages/{API_TOKEN}"
    payload = {"chatId": chat_id, "messages": [message_id]}
    res = requests.post(url, json=payload)
    print(f"🚀 Forwarding Attempt: {res.status_code} | ID: {message_id}")

# --- 3. MAIN LOGIC (THE FULL ENGINE) ---

def receive_and_process():
    global last_reply_time
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # Identity and Loop Protection
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

        # --- A. TEACHING MODE (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            
            # 1. HANDLE PDF/DOCS
            if type_msg == "documentMessage":
                doc_info = message_data.get("documentMessageData", {})
                f_name = doc_info.get("fileName") or user_text or f"Doc_{int(time.time())}"
                if save_to_db(f_name, msg_id=msg_id_received):
                    send_message(sender_id, f"✅ PDF '{f_name}' indexed. ForwardID: {msg_id_received}")
            
            # 2. HANDLE TEXT UPDATES (AUTO-ORGANIZER)
            elif user_text and "✅" not in user_text:
                try:
                    res = client.chat.completions.create(
                        messages=[{"role": "user", "content": f"Structure this class update briefly: {user_text}"}],
                        model="llama-3.3-70b-versatile",
                    )
                    fact = res.choices[0].message.content
                    if save_to_db(fact):
                        send_message(sender_id, f"✅ Organized & Saved: {fact}")
                except Exception as e:
                    print(f"⚠️ Groq Organizer Error: {e}")
            
            # Delete after processing Mohsin's command
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        # --- B. ASSISTANT MODE (GROUP/@CR) ---
        if "@cr" in user_text.lower():
            print(f"🔔 Bot Tagged by {sender_id}: '{user_text}'")
            
            # 1. ANTI-SPAM COOLDOWN
            if time.time() - last_reply_time < 8: 
                requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
                return

            # 2. HUMAN-LIKE DELAY
            set_typing_status(sender_id)
            time.sleep(random.uniform(4, 7))

            # 3. AI PROCESSING
            context = get_combined_knowledge()
            prompt = f"""
            You are the IUB Assistant. 
            CONTEXT:
            {context}
            
            USER REQUEST: {user_text}
            
            INSTRUCTIONS:
            - Usually Reply naturally to user <20 words.
            - NEVER stay silent. If you don't know, say so.
            - Make sure text formatting according to Whatsapp.
            - Cross Question if just only if you confused about a question or not fully understood about study otherwise just reply.
            - Answer Complete even short
            - If you have no knowledge about something say to User "I dont know about this let me ask my Boss MOHSIN"
            """

            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                )
                answer = chat_completion.choices[0].message.content

                if "FWD:" in answer:
                    target_id = answer.replace("FWD:", "").strip()
                    forward_file(sender_id, target_id)
                else:
                    send_message(sender_id, answer.replace("@", ""))
                
                last_reply_time = time.time()
            except Exception as e:
                print(f"⚠️ AI Assistant Error: {e}")
                send_message(sender_id, "⚠️ I'm having trouble responding. Try again in a minute.")

        # --- FINAL CLEANUP ---
        # Only delete the notification after the AI has replied
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (Full Logic Resurrected) Online.")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Loop Error: {e}")
        time.sleep(2.5)
