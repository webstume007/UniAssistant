
import os
from dotenv import load_dotenv
from whatsapp_chatbot_python import GreenAPIBot, Notification
from brain import get_ai_response

load_dotenv()

# Load class data
def load_context():
    try:
        with open("knowledge_base.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "No class data available."

bot = GreenAPIBot(
    os.getenv("GREEN_API_ID_INSTANCE"),
    os.getenv("GREEN_API_TOKEN")
)

@bot.router.message(type_message="text")
def message_handler(notification: Notification):
    chat_id = notification.chat
    user_text = notification.message_text
    sender_name = notification.event_payload.get("senderData", {}).get("senderName", "Student")

    # LOGIC: Only respond if the message is in a group AND the bot is mentioned
    # You can change '@bot' to whatever your bot's name is in the group
    if "@bot" in user_text.lower() or "assistant" in user_text.lower():
        print(f"Group Query from {sender_name}: {user_text}")

        # Clean the message (remove the @bot tag before sending to AI)
        clean_query = user_text.lower().replace("@bot", "").strip()

        # 1. Get the context
        context = load_context()

        # 2. Get the response from Gemini
        ai_reply = get_ai_response(clean_query, context)

        # 3. Reply to the group (tagging the sender)
        final_message = f"@{sender_name}, {ai_reply}"
        notification.answer(final_message)

if __name__ == "__main__":
    print("IUB Group Assistant is online and listening...")
    bot.run_forever()
