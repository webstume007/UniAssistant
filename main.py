import os
from google import genai
from whatsapp_chatbot_python import GreenAPIBot, Notification

# 1. Fetch Variables
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# 2. Safety Check - This stops the crash and tells you what's wrong
if not GEMINI_KEY:
    print("❌ ERROR: GEMINI_API_KEY is missing in Railway Variables!")
    exit(1)
if not ID_INSTANCE or not API_TOKEN:
    print("❌ ERROR: WhatsApp (Green-API) credentials are missing!")
    exit(1)

# 3. Initialize AI & Bot
try:
    client = genai.Client(api_key=GEMINI_KEY)
    bot = GreenAPIBot(
        ID_INSTANCE, 
        API_TOKEN, 
        host="https://7103.api.greenapi.com"
    )
except Exception as e:
    print(f"❌ ERROR initializing services: {e}")
    exit(1)

def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "I am the IUB Assistant. My boss is Mohsin Akhtar."

@bot.router.message(type_message="text")
def message_handler(notification: Notification):
    user_text = notification.message_text
    sender_name = notification.event_payload.get("senderData", {}).get("senderName", "Student")
    
    if "bot" in user_text.lower() or "assistant" in user_text.lower():
        print(f"Processing query from {sender_name}...")
        query = user_text.lower().replace("@bot", "").strip()
        context = get_knowledge()
        
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=f"Context: {context}\n\nQuestion: {query}"
            )
            notification.answer(f"@{sender_name}, {response.text}")
        except Exception as e:
            print(f"⚠️ AI Error: {e}")
            notification.answer("Sorry, my brain is having a temporary issue. Try again in a minute!")

if __name__ == "__main__":
    print("✅ IUB Assistant is Connected and Listening on Railway!")
    bot.run_forever()
