import requests
from config import SALON_INFO

API_KEY = "ajp6Ch80M9Uhi8XDy69Bdd5g8hQFQCUNw0y5SjBX"

chat_sessions = {}

def ask_gemini(user_id: int, user_message: str) -> str:
    try:
        if user_id not in chat_sessions:
            chat_sessions[user_id] = []

        history = chat_sessions[user_id]

        if len(history) == 0:
            full_message = f"{SALON_INFO}\n\nВопрос клиента: {user_message}"
        else:
            full_message = user_message

        history.append({"role": "USER", "message": full_message})

        payload = {
            "model": "command-a-03-2025",
            "chat_history": history[:-1],
            "message": full_message
        }

        resp = requests.post(
            "https://api.cohere.ai/v1/chat",
            json=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        resp.raise_for_status()

        answer = resp.json()["text"]
        history.append({"role": "CHATBOT", "message": answer})

        return answer

    except Exception as e:
        print(f"Cohere error: {e}")
        return "Извините, произошла ошибка. Для связи с нами позвоните: +7 (383) 123-45-67"

def reset_chat(user_id: int):
    if user_id in chat_sessions:
        del chat_sessions[user_id]