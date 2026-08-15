import io
import aiohttp
from aiogram import Bot

class ImgBBUploader:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def upload_telegram_photo(self, bot: Bot, file_id: str) -> str:
        try:
            tg_file = await bot.get_file(file_id)
            buffer = io.BytesIO()
            await bot.download_file(tg_file.file_path, buffer)
            buffer.seek(0)

            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('key', self.api_key)
                data.add_field('image', buffer, filename='cover.jpg')
                async with session.post('https://api.imgbb.com/1/upload', data=data) as resp:
                    result = await resp.json()
                    if result.get("success"):
                        return result["data"]["url"]
        except Exception as e:
            print(f"[ImgBB Error] {e}")
        return ""
