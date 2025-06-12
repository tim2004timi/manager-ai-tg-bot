from minio import Minio
from io import BytesIO
import os


APP_HOST = os.getenv("APP_HOST", "localhost")

BUCKET_NAME = "psih-photo"
minio_client = Minio(
    endpoint="localhost:9000",
    access_key="admin",
    secret_key="password123",
    secure=False  # True для HTTPS
)

async def upload_to_minio(file_data: bytes, file_name: str) -> str:
    try:
        with BytesIO(file_data) as file_stream:
            minio_client.put_object(
                bucket_name=BUCKET_NAME,
                object_name=file_name,
                data=file_stream,
                length=len(file_data),
                content_type="image/jpeg"
            )
        return f"http://{APP_HOST}:9000/{BUCKET_NAME}/{file_name}"
    except Exception as e:
        print(f"Upload error: {e}")
        raise