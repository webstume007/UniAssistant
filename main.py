import os, time, requests
from google import genai

# 1. Configuration & Key Pool
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
BOT_PHONE = "923468415931" 

# Collect all available keys into a list
keys = [os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_KEY_2"), os.environ.get("GEMINI_KEY_3")]
api_keys = [k for k in keys if k] # Remove empty ones
current_key_index = 0

BASE_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

def get_ai_response(prompt):
    global current_key_index
    # We will try the model across our pool of keys
    for _ in range(len(api_keys)):
        try:
            active_key = api_keys[current_key_index]
            client = genai.Client(api_key=active_key)
            
            # Use the most stable 2026 model
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite", 
                contents=prompt
            )
            return response.text
        except Exception as e:
            if "429" in str(e):
                print(f"⚠️ Key {current_key_index} exhausted. Rotating...")
                current_key_index = (current_key_index + 1) % len(api_keys)
                continue # Try again with the next key
            else:
                print(f"⚠️ AI Error: {e}")
                return None
    return "All AI keys are currently at their limit. Try again in 1 minute."

def receive_and_process():
    receive_url = f"{BASE_URL}/receiveNotification/{API_TOKEN}"
    response = requests.get(receive_url)
    
    if response.status_code == 200 and response.json():
        data = response.json()
        receipt_id = data.get("receiptId")
        body = data.get("body", {})
        sender_id = body.get("senderData", {}).get("chatId", "")
        
        if BOT_PHONE in sender_id:
            requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")
            return

        message_data = body.get("messageData", {})
        user_text = message_data.get("textMessageData", {}).get("textMessage", "") or \
                    message_data.get("extendedTextMessageData", {}).get("text", "")

        if user_text and "@cr" in user_text.lower():
            print(f"📩 Processing @CR request via Key Index {current_key_index}...")
            
            # Keeping the prompt small saves 'Input Token' quota
            system_info = "You are IUB AI Assistant. Only answer class info. Short answers only."
            answer = get_ai_response(f"{system_info}\n\nQuestion: {user_text}")
            
            if answer:
                url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
                requests.post(url, json={"chatId": sender_id, "message": answer})
                print("📤 Replied!")

        requests.delete(f"{BASE_URL}/deleteNotification/{API_TOKEN}/{receipt_id}")

if __name__ == "__main__":
    print(f"🚀 IUB Bot Online with {len(api_keys)} API keys.")
    while True:
        try:
            receive_and_process()
        except Exception as e:
            print(f"⚠️ System Error: {e}")
        time.sleep(1.5)
