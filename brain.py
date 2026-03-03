import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """
You are the 'Mohsin's AI Assistant'. You assist IUB University students in a public WhatsApp group.
- Your answers must be concise and helpful (don't write long essays in a group chat).
- Use the 'Class Data Context' provided to answer questions about schedules, assignments, and IUB news.
- If a student is being rude or spamming, remain professional.
- You can speak in English or Roman Urdu.
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT
)

def get_ai_response(user_query, context_data):
    full_prompt = f"Context: {context_data}\n\nQuestion: {user_query}"
    response = model.generate_content(full_prompt)
    return response.text
