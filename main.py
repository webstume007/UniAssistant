import os
from google import genai
from whatsapp_chatbot_python import GreenAPIBot, Notification

# 1. Fetch Variables and Check for 'None'
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Safety Check: If these are None, the bot won't start
if not ID_INSTANCE or not API_TOKEN:
    print("❌ ERROR: GREEN_API variables are missing in Railway Settings!")
    exit(1)

# 2. Initialize New Gemini SDK
client = genai.Client(api_key=GEMINI_KEY)

# 3. Initialize WhatsApp Bot
bot = GreenAPIBot(ID_INSTANCE, API_TOKEN)

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
    
    # Respond only if tagged
    if "@bot" in user_text.lower():
        print(f"Processing query from {sender_name}...")
        
        query = user_text.lower().replace("@bot", "").strip()
        context = get_knowledge()
        
        # Using the new 2026 Gemini 2.0/3.0 model call
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"Context: {context}\n\nQuestion: {query}"
        )
        
        notification.answer(f"@{sender_name}, {response.text}")

if __name__ == "__main__":
    print("✅ IUB Assistant is now Online on Railway!")
    bot.run_forever()
