import os
from google import genai
from whatsapp_chatbot_python import GreenAPIBot, Notification

# 1. Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# 2. Setup AI
client = genai.Client(api_key=GEMINI_KEY)

# 3. Setup Bot (With your specific Host)
bot = GreenAPIBot(
    ID_INSTANCE, 
    API_TOKEN, 
    host="https://7103.api.greenapi.com"
)

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
    
    # Respond only if @bot is mentioned
    if "@bot" in user_text.lower():
        print(f"User {sender_name} is asking something...")
        
        query = user_text.lower().replace("@bot", "").strip()
        context = get_knowledge()
        
        # Generate Answer
        response = client.models.generate_content(
            model="gemini-1.5-flash", # Fast and reliable
            contents=f"Context: {context}\n\nQuestion: {query}"
        )
        
        # Reply in Group
        notification.answer(f"@{sender_name}, {response.text}")

if __name__ == "__main__":
    print("✅ IUB Assistant is Connected and Listening!")
    bot.run_forever()
