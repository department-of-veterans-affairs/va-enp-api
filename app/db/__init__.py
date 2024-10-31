import os

from dotenv import load_dotenv
from loguru import logger

DB_NAME = os.getenv('DB_NAME', '')

if not DB_NAME:
    logger.info('Environment variables not set. Loading them from ".env.example" file')
    load_dotenv('.env.example')
    DB_NAME = os.getenv('DB_NAME', '')


DB_READ_URI = os.getenv('DB_READ_URI', '')
DB_WRITE_URI = os.getenv('DB_WRITE_URI', '')
