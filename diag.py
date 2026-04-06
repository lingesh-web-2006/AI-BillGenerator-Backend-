import os
from dotenv import load_dotenv

load_dotenv()

print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
print(f"DB_URL: {os.getenv('DB_URL')}")
print(f"DB_HOST: {os.getenv('DB_HOST')}")
print(f"DB_PORT: {os.getenv('DB_PORT')}")
print(f"DB_NAME: {os.getenv('DB_NAME')}")
print(f"DB_USER: {os.getenv('DB_USER')}")
