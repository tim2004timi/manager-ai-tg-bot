from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from shared import get_bot
import asyncio

app = FastAPI()

app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # В продакшене укажите конкретные домены
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )

class WebhookMessage(BaseModel):
    answer: str
    chat_id: str

@app.post("/webhook/messages")
async def webhook(message: WebhookMessage):
    try:
        # Convert chat_id to integer
        chat_id = int(message.chat_id)
        
        # Create a new bot instance
        bot = get_bot()
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message.answer
            )
        finally:
            await bot.session.close()
        
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 