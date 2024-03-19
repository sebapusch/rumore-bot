import base64
import os
import random

from openai import AsyncOpenAI

from constants import MOOD_PHRASES

def totti():
    with open("junk/barzellette.txt", "r") as file:
        lines = file.read().split("\n\n")
        msg = random.choice(lines)
    return msg


async def gpt(mood: str, fullname: str) -> str:
    client = AsyncOpenAI()

    prompt = f"{fullname} sta {mood}. Inventa una storia per adulti ridicola adatta all'umore."
    chat_completion = await client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": prompt,
            }
        ],
        model="gpt-3.5-turbo-0125",
    )
    return chat_completion.choices[0].message.content


async def mood_message(mood: int, user: str, info: list[str]) -> str:
    message = await gpt(MOOD_PHRASES[mood], user)
    return f"@{user} eccoti una storia:\n{message}"


async def generate_image(prompt: str) -> bytes:
    img = await client.images.generate(
        model='dall-e-2',
        prompt=prompt,
        quality="standard",
        n=1,
        response_format="b64_json",
        size="256x256"
    )

    return base64.b64decode(img.data[0].b64_json)
