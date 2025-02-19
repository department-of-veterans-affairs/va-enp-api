import json
import os

DB_ENGINE = 'postgresql+psycopg'

DB_AUTH = json.loads(os.getenv('DB_AUTH', '{"username": "postgres", "password": "LocalPassword"}'))
DB_USERNAME = DB_AUTH['username']
DB_PASSWORD = DB_AUTH['password']

DB_HOSTNAME = os.getenv('DB_HOSTNAME', 'localhost')
DB_HOSTNAME_READ = os.getenv('DB_HOSTNAME_READ', 'localhost')

DB_PORT = os.getenv('DB_PORT', '5432')

DB_NAME = os.getenv('DB_NAME', 'va_enp_api')

# DB_READ_URI = os.getenv('DB_READ_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/va-enp-api-db')
# DB_WRITE_URI = os.getenv('DB_WRITE_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/va-enp-api-db')
DB_READ_URI = f'{DB_ENGINE}://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOSTNAME_READ}:{DB_PORT}/{DB_NAME}'
DB_WRITE_URI = f'{DB_ENGINE}://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOSTNAME}:{DB_PORT}/{DB_NAME}'
