import os
import time
import requests
from groq import Groq
from supabase import create_client

# --- 1. CONFIGURATION ---
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
SUPA_URL = os.environ.get("SUPABASE_URL")
SUPA_KEY = os.environ.get("SUPABASE_KEY")

# Replace with your actual IDs (e.g., "923001234567@c.us")
BOT_PHONE = "923468415931@c.us" 
MOHSIN_PHONE = "923XXXXXXXXX@c.us" 

# Initialize Clients
client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPA_URL, SUPA_KEY)
BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

# --- 2. HELPER FUNCTIONS ---

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
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "IUB AI Assistant. Developed by Mohsin Akhtar."

def send_message(chat_id, text):
    """Sends a WhatsApp message via Green-API."""
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    requests.post(url, json=payload)

# --- 3. MAIN PROCESSING LOGIC ---

def receive_and_process():
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        
        # Get Sender Details
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        # LOOP KILLER: Stop if the bot is talking to itself
        if sender_id == BOT_PHONE:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        # Extract Message Text
        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        if user_text:
            # A. TEACHING MODE: If Mohsin sends a message, save it
            if sender_id == MOHSIN_PHONE:
                if save_to_supabase(user_text):
                    send_message(sender_id, "✅ Learned and saved to Cloud Database, Mohsin.")
                else:
                    send_message(sender_id, "⚠️ Failed to save to Database. Check Railway logs.")
            
            # B. ASSISTANT MODE: Respond to @CR
            elif "@cr" in user_text.lower():
                print(f"📩 Processing @CR request from {sender_id}...")
                
                # Combine GitHub text + Cloud Database info
                context = f"{get_local_knowledge()} {get_cloud_knowledge()}"
                
                try:
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {
                                "role": "system", 
                                "content": f"You are the IUB AI Assistant. Context: {context}. Rules: 1. Reply under 25 words. 2. Be helpful. 3. NEVER mention @CR."
                            },
                            {"role": "user", "content": user_text}
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                    
                    answer = chat_completion.choices[0].message.content
                    # Final safety check to strip tags
                    clean_answer = answer.replace("@", "")
                    
                    send_message(sender_id, clean_answer)
                    print("📤 Reply Sent!")

                except Exception as e:
                    print(f"⚠️ Groq AI Error: {e}")

        # Always delete notification to clear the queue
        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

# --- 4. EXECUTION LOOP ---

if __name__ == "__main__":
    print("🚀 IUB Assistant (Supabase Cloud Mode) is starting...")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5) # Prevent CPU overload
