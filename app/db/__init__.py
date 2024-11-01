import os

DB_NAME = os.getenv('DB_NAME', 'va-enp-api-db')
DB_READ_URI = os.getenv('DB_READ_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/va-enp-api-db')
DB_WRITE_URI = os.getenv('DB_WRITE_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/va-enp-api-db')
