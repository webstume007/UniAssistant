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
# Use "@g.us" for group IDs if you want to restrict to one group
BOT_PHONE = "923468415931@c.us" 
MOHSIN_PHONE = "923053296062@c.us" # Replace with your personal number

# Initialize Clients
client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

# --- 2. KNOWLEDGE & DATA FUNCTIONS ---

def save_to_supabase(text):
    """Saves Mohsin's updates to the cloud database."""
    try:
        supabase.table("knowledge").insert({"info": text}).execute()
        return True
    except Exception as e:
        print(f"❌ Supabase Save Error: {e}")
        return False

def get_cloud_knowledge():
    """Retrieves all info learned from Mohsin's texts."""
    try:
        data = supabase.table("knowledge").select("info").execute()
        return " ".join([row['info'] for row in data.data])
    except:
        return ""

def get_local_knowledge():
    """Reads the static knowledge_base.txt from GitHub."""
    try:
        if os.path.exists("knowledge_base.txt"):
            with open("knowledge_base.txt", "r") as f:
                return f.read()
        return ""
    except:
        return "IUB AI Assistant (Semester 3)."

# --- 3. WHATSAPP UI FUNCTIONS (The Safety Shield) ---

def set_typing_status(chat_id):
    """Tells WhatsApp the bot is 'composing' to look human."""
    url = f"{BASE_URL}/setPresence/{API_TOKEN}"
    payload = {"chatId": chat_id, "presence": "composing"}
    try:
        requests.post(url, json=payload)
    except:
        pass

def send_message(chat_id, text):
    """Sends the actual message."""
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

# --- 4. MAIN PROCESSING LOGIC ---

def receive_and_process():
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # 1. ANTI-LOOP & IDENTITY CHECK
        if sender_id == BOT_PHONE:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        if user_text:
            # 2. TEACHING MODE: Updates from Mohsin
            if sender_id == MOHSIN_PHONE:
                if save_to_supabase(user_text):
                    send_message(sender_id, "✅ Data saved to cloud memory, Mohsin.")
                else:
                    send_message(sender_id, "⚠️ Database Error. Check logs.")
            
            # 3. ASSISTANT MODE: Respond to @CR
            elif "@cr" in user_text.lower():
                print(f"📩 Processing @CR request from {sender_id}...")
                
                # HUMAN SIMULATION: Random initial wait (1-3 seconds)
                time.sleep(random.uniform(1.0, 3.0))
                set_typing_status(sender_id)
                
                # HUMAN SIMULATION: "Thinking" time based on message length
                time.sleep(random.uniform(2.5, 5.0))
                
                # Gather Knowledge
                context = f"{get_local_knowledge()} {get_cloud_knowledge()}"
                
                try:
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {
                                "role": "system", 
                                "content": f"You are the IUB Assistant. Context: {context}. Rule: Be natural and helpful. Reply in <25 words. NEVER use the word '@CR' or tag users."
                            },
                            {"role": "user", "content": user_text}
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                    
                    answer = chat_completion.choices[0].message.content
                    clean_answer = answer.replace("@", "") # Strip tags to prevent loops
                    
                    send_message(sender_id, clean_answer)
                    print("📤 Safe Reply Sent!")

                except Exception as e:
                    print(f"⚠️ Groq AI Error: {e}")

        # Always delete the notification
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

# --- 5. EXECUTION LOOP ---

if __name__ == "__main__":
    print("🚀 IUB Assistant (Safe Cloud Mode) is starting...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        # Randomize polling slightly to avoid a perfect 2-second heartbeat
        time.sleep(random.uniform(1.5, 2.5))
