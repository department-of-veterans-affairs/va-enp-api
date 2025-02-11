import os


API_DB_READ_URI = os.getenv('API_DB_READ_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/enp_api')
API_DB_WRITE_URI = os.getenv('API_DB_WRITE_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/enp_api')

DB_NAME = os.getenv('DB_NAME', 'enp_api')
DB_READ_URI = os.getenv('DB_READ_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/enp_api')
DB_WRITE_URI = os.getenv('DB_WRITE_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/enp_api')
