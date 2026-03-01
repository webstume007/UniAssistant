import os
from google import genai
from whatsapp_chatbot_python import GreenAPIBot, Notification

# Configuration
ID_INSTANCE = os.environ.get("GREEN_API_ID_INSTANCE")
API_TOKEN = os.environ.get("GREEN_API_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_KEY)
bot = GreenAPIBot(ID_INSTANCE, API_TOKEN, host="https://7103.api.greenapi.com")

@bot.router.message() # This will catch EVERY message now
def message_handler(notification: Notification):
    # This will print the actual text to your Railway logs
    print(f"RAW NOTIFICATION: {notification.event}")
    
    user_text = notification.message_text
    sender_name = notification.event_payload.get("senderData", {}).get("senderName", "Student")
    
    # We will reply to EVERYTHING for now just to test
    print(f"I heard: {user_text}")
    
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=f"You are a test bot. Someone said: {user_text}. Reply shortly."
    )
    
    notification.answer(f"Test Reply for {sender_name}: {response.text}")

if __name__ == "__main__":
    bot.run_forever()
