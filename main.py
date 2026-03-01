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
        data = {"info": info_text}
        if msg_id:
            data["message_id"] = msg_id
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
                # We label it as 'FILE' to help the AI recognize it
                history.append(f"FILE: '{row['info']}' (ID: {row['message_id']})")
            else:
                history.append(f"FACT: {row['info']}")
        return "\n".join(history)
    except: return ""

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage/{API_TOKEN}", json={"chatId": chat_id, "message": text})

def forward_file(chat_id, message_id):
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
        
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
        if sender_id == BOT_PHONE: return

        message_data = body.get("messageData", {})
        msg_id_received = body.get("idMessage")
        type_msg = message_data.get("typeMessage")
        
        # Extract Text/Caption
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "") or \
                    message_data.get("documentMessageData", {}).get("caption", "") or ""

        # --- A. TEACHING MODE (MOHSIN) ---
        if sender_id == MOHSIN_PHONE and "@cr" not in user_text.lower():
            
            # --- HANDLE PDF (FIXED NAMING) ---
            if type_msg == "documentMessage":
                doc_info = message_data.get("documentMessageData", {})
                
                # FIX: Prioritize real filename over static text
                real_filename = doc_info.get("fileName")
                save_name = real_filename if real_filename else (user_text if user_text else "Unnamed_File")
                
                if save_to_db(save_name, msg_id=msg_id_received):
                    send_message(sender_id, f"✅ Indexed PDF: {save_name}")
                return

            # --- HANDLE TEXT UPDATE ---
            if user_text and "✅" not in user_text:
                res = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"Structure this: {user_text}"}],
                    model="llama-3.3-70b-versatile",
                )
                fact = res.choices[0].message.content
                if save_to_db(fact):
                    send_message(sender_id, f"✅ Saved Fact: {fact}")
            return

        # --- B. ASSISTANT MODE (GROUP) ---
        if "@cr" in user_text.lower():
            if time.time() - last_reply_time < 8: return

            requests.post(f"{BASE_URL}/setPresence/{API_TOKEN}", json={"chatId": sender_id, "presence": "composing"})
            time.sleep(random.uniform(4, 7))

            context = get_combined_knowledge()
            
            # UPDATED SEARCH PROMPT
            prompt = f"""
            Context: {context}
            User Question: {user_text}
            
            Instruction:
            1. Search the Context for any 'FILE' that matches the user's request keywords.
            2. If a match is found, reply ONLY with 'FWD:' + the ID associated with that file.
            3. If multiple files match, pick the most relevant one.
            4. If no file matches, provide a short natural answer based on 'FACTS'.
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
                    print(f"➡️ Forwarded File ID: {target_id}")
                else:
                    send_message(sender_id, answer.replace("@", ""))
                
                last_reply_time = time.time()
            except Exception as e: print(f"⚠️ AI Error: {e}")

if __name__ == "__main__":
    print("🚀 IUB Assistant (File Naming Fixed) Online.")
    while True:
        try: receive_and_process()
        except: pass
        time.sleep(2.5)
