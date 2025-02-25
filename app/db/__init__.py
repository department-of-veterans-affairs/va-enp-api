import json
import os

DB_ENGINE = 'postgresql+psycopg'

ENP_DB_NAME = os.getenv('ENP_DB_NAME', 'va_enp_api')
ENP_DB_PORT = os.getenv('ENP_DB_PORT', '5433')

# These configs require a change in infra to be updated
DB_AUTH = json.loads(os.getenv('DB_AUTH', '{"username": "postgres", "password": "LocalPassword"}'))
DB_USERNAME = DB_AUTH['username']
DB_PASSWORD = DB_AUTH['password']

ENP_DB_HOSTNAME = os.getenv('DB_HOSTNAME', 'localhost')
ENP_DB_HOSTNAME_READ = os.getenv('DB_HOSTNAME_READ', 'localhost')

# get the notification api database URI
NAPI_DB_READ_URI = os.getenv(
    'NAPI_DB_READ_URI', f'{DB_ENGINE}://postgres:LocalPassword@localhost:5432/notification_api'
)
NAPI_DB_WRITE_URI = os.getenv(
    'NAPI_DB_WRITE_URI', f'{DB_ENGINE}://postgres:LocalPassword@localhost:5432/notification_api'
)

# Ensure the correct DB_ENGINE is used. This is necessary when deployed.
NAPI_DB_READ_URI = DB_ENGINE + '://' + NAPI_DB_READ_URI.split('://')[1]
NAPI_DB_WRITE_URI = DB_ENGINE + '://' + NAPI_DB_WRITE_URI.split('://')[1]

# Construct the ENP database URIs
ENP_DB_READ_URI = f'{DB_ENGINE}://{DB_USERNAME}:{DB_PASSWORD}@{ENP_DB_HOSTNAME_READ}:{ENP_DB_PORT}/{ENP_DB_NAME}'
ENP_DB_WRITE_URI = f'{DB_ENGINE}://{DB_USERNAME}:{DB_PASSWORD}@{ENP_DB_HOSTNAME}:{ENP_DB_PORT}/{ENP_DB_NAME}'
