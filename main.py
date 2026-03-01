import os
import google.generativeai as genai
from whatsapp_chatbot_python import GreenAPIBot, Notification

# 1. Setup Gemini AI
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. Setup WhatsApp Bot
bot = GreenAPIBot(
    os.environ.get("GREEN_API_ID_INSTANCE"), 
    os.environ.get("GREEN_API_TOKEN")
)

# 3. Load Knowledge Base
def get_knowledge():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except:
        return "I am the IUB Assistant. My boss is Mohsin Akhtar."

@bot.router.message(type_message="text")
def message_handler(notification: Notification):
    user_text = notification.message_text
    sender_name = notification.event_payload.get("senderData", {}).get("senderName", "Student")
    
    # Check if the bot is tagged
    if "@bot" in user_text.lower():
        print(f"Processing message from {sender_name}...")
        
        # Clean the query
        query = user_text.lower().replace("@bot", "").strip()
        
        # Prepare Prompt
        context = get_knowledge()
        prompt = f"Context: {context}\n\nQuestion from {sender_name}: {query}\nAnswer:"
        
        # Generate and Send
        response = model.generate_content(prompt)
        notification.answer(f"@{sender_name} {response.text}")

if __name__ == "__main__":
    print("Railway Bot is starting...")
    bot.run_forever()
