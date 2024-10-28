import os

from dotenv import load_dotenv
from loguru import logger

DB_NAME = os.getenv('DB_NAME')
logger.info(f'{DB_NAME=}', 'NOT FOUND')

if DB_NAME == 'NOT FOUND':
    logger.info('Loading environment variables from .local.env file')
    load_dotenv('../../ci/.local.env')

DB_READ_URI = os.getenv('DB_READ_URI', 'NOT FOUND')
DB_WRITE_URI = os.getenv('DB_WRITE_URI', 'NOT FOUND')
