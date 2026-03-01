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

# --- 2. DATA FUNCTIONS ---

def save_to_db(info_text, msg_id=None):
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
    try:
        data = supabase.table("knowledge").select("info", "message_id").execute()
        context_lines = []
        for row in data.data:
            if row.get('message_id'):
                context_lines.append(f"DATABASE_FILE: Name='{row['info']}', MessageID='{row['message_id']}'")
            else:
                context_lines.append(f"FACT: {row['info']}")
        return "\n".join(context_lines)
    except: return "No data in database yet."

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage/{API_TOKEN}", json={"chatId": chat_id, "message": text})

def forward_file(chat_id, message_id):
    url = f"{BASE_URL}/forwardMessages/{API_TOKEN}"
    payload = {"chatId": chat_id, "messages": [message_id]}
    res = requests.post(url, json=payload)
    print(f"🚀 Forwarding Attempt: {res.status_code} | ID: {message_id}")

# --- 3. MAIN LOGIC ---

def receive_and_process():
    global last_reply_time
    response = requests.get(f"{BASE_URL}/receiveNotification/{API_TOKEN}")
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # DELETE IMMEDIATELY
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
        if sender_id == BOT_PHONE: return

        message_data = body.get("messageData", {})
        msg_id_received = body.get("idMessage")
        type_msg = message_data.get("typeMessage")
        
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "") or \
                    message_data.get("documentMessageData", {}).get("caption", "") or ""

        # --- A. TEACHING MODE (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            if type_msg == "documentMessage":
                doc_info = message_data.get("documentMessageData", {})
                f_name = doc_info.get("fileName") or user_text or f"File_{int(time.time())}"
                if save_to_db(f_name, msg_id=msg_id_received):
                    send_message(sender_id, f"✅ PDF Indexed: {f_name}")
                return

            if user_text and "✅" not in user_text:
                res = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"Structure this: {user_text}"}],
                    model="llama-3.3-70b-versatile",
                )
                fact = res.choices[0].message.content
                if save_to_db(fact):
                    send_message(sender_id, f"✅ Saved: {fact}")
            return

        # --- B. ASSISTANT MODE (GROUP) ---
        if "@cr" in user_text.lower():
            if time.time() - last_reply_time < 5: return

            requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": sender_id, "presence": "composing"})
            time.sleep(random.uniform(2, 4))

            context = get_combined_knowledge()
            
            # REFINED SYSTEM PROMPT FOR BETTER REPLIES
            prompt = f"""
            You are the IUB Assistant. 
            CONTEXT FROM DATABASE:
            {context}
            
            USER REQUEST: {user_text}
            
            INSTRUCTIONS:
            1. If the user asks for a file (PDF/Image), search the Context for a Name that matches.
            2. If you find a matching 'DATABASE_FILE', reply ONLY with: FWD: [MessageID]
            3. If you CANNOT find the file, reply naturally saying you don't have that file yet.
            4. If it's a general question, use the 'FACTS' to answer briefly.
            5. NEVER remain silent. Always provide a response.
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
                    # Ensure no tags are in the final reply
                    send_message(sender_id, answer.replace("@", ""))
                
                last_reply_time = time.time()
            except Exception as e:
                print(f"⚠️ AI Error: {e}")
                send_message(sender_id, "⚠️ I'm having trouble thinking right now. Please try again.")

if __name__ == "__main__":
    print("🚀 IUB Assistant (V4 - Always Reply) Online.")
    while True:
        try: receive_and_process()
        except: pass
        time.sleep(2)
