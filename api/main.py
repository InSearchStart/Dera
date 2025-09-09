import os
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

TOKEN = os.getenv('TOKEN')
TOKEN_DEEP_SEEK = os.getenv('TOKEN_DEEP_SEEK')

if not TOKEN:
    raise ValueError("Bot token is not set in environment variables!")

app = FastAPI()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=TOKEN_DEEP_SEEK,
)

MAX_MESSAGE_LENGTH = 4096 

def split_text(text, max_length=MAX_MESSAGE_LENGTH):
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]

async def generate_response(text: str):
    try:
        completion = await client.chat.completions.create(
            model="deepseek/deepseek-r1-0528:free",
            messages=[{"role": "user", "content": text}],
        )
        return completion.choices[0].message.content
    except Exception as e:
        print("Ошибка при генерации ответа:", e)
        return "Произошла ошибка при обработке вашего запроса."

def parse_message(message):
    if "message" not in message or "text" not in message["message"]:
        return None, None  

    chat_id = message["message"]["chat"]["id"]
    txt = message["message"]["text"]
    return chat_id, txt

@app.post('/setwebhook')
async def setwebhook():
    webhook_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={os.environ.get('VERCEL_URL')}/webhook&allowed_updates=%5B%22message%22,%22callback_query%22%5D"
    async with httpx.AsyncClient() as client:
        response = await client.get(webhook_url)

    if response.status_code == 200:
        return JSONResponse(content={"status": "Webhook successfully set"}, status_code=200)
    else:
        return JSONResponse(content={"error": f"Error setting webhook: {response.text}"}, status_code=response.status_code)

@app.on_event("startup")
async def startup_event():
    await set_webhook()


async def tel_send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "Открыть Муз Чат", "web_app": {"url": "https://dancerlist.github.io/Year/"}},
                    {"text": "Диалог с ИИ", "callback_data": "deepSeek"}
                ]
            ]
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)

    if response.status_code != 200:
        print("Ошибка отправки сообщения:", response.text)

    return response

async def tel_send_message_not_markup(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)

    if response.status_code != 200:
        print("Ошибка отправки сообщения:", response.text)

    return response

user_states = {}

async def process_user_request(chat_id, txt):
    await tel_send_message_not_markup(chat_id, '🏈 Идет обработка...')
    response_text = await generate_response(txt)
    for part in split_text(response_text):
        await tel_send_message_not_markup(chat_id, part)
    user_states[chat_id] = None 

@app.post('/webhook')
async def webhook(request: Request, background_tasks: BackgroundTasks):
    msg = await request.json()
    print("Получен вебхук:", msg)

    if "callback_query" in msg:
        callback = msg["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        callback_data = callback["data"]

        if callback_data == "deepSeek":
            await tel_send_message_not_markup(chat_id, "Вы выбрали диалог с ИИ. Как я могу помочь вам?")
            user_states[chat_id] = 'awaiting_response'
            return JSONResponse(content={"status": "message_sent"}, status_code=200)

        return JSONResponse(content={"status": "deleted"}, status_code=200)

    chat_id, txt = parse_message(msg)
    if chat_id is None or txt is None:
        return JSONResponse(content={"status": "ignored"}, status_code=200)

    if chat_id in user_states and user_states[chat_id] == "awaiting_response":
        background_tasks.add_task(process_user_request, chat_id, txt)

    elif txt.lower() == "/start":
        await tel_send_message(chat_id, 
            "🎵 Добро пожаловать в наш уникальный музыкальный мир! "
            "Здесь вас ждут любимые треки и вдохновляющие клипы. 🎶\n\n"
            "✨ Мечтаете о персональной композиции? "
            "Закажите эксклюзивное музыкальное произведение, созданное специально для вас! 🎼\n\n"
            "🤖 Используйте возможности искусственного интеллекта для творческих запросов и новых идей. 🚀"
        )

    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.get("/")
async def index():
    return "<h1>Telegram Bot Webhook is Running</h1>"

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)), log_level="info")
