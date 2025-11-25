import base64
import os

import aiofiles


def image_to_base64(file_path: str) -> str:
    b64_bytes = base64.b64encode(file_path.read_bytes())
    data_uri = "data:image/png;base64," + b64_bytes.decode()
    return data_uri


async def save_byte_file(byte_file, destination_folder, filename):
    os.makedirs(destination_folder, exist_ok=True)
    destination_path = os.path.join(destination_folder, filename)
    async with aiofiles.open(str(destination_path), "wb") as buffer:
        while content := await byte_file.read(1024 * 1024):
            await buffer.write(content)
    return destination_path
