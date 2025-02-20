import os

ENP_DB_NAME = os.getenv('DB_NAME', 'va-enp-api-db')
ENP_DB_READ_URI = os.getenv(
    'ENP_DB_READ_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5433/va-enp-api-db'
)
ENP_DB_WRITE_URI = os.getenv(
    'ENP_DB_WRITE_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5433/va-enp-api-db'
)

NAPI_DB_READ_URI = os.getenv(
    'API_DB_READ_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/notification_api'
)
NAPI_DB_WRITE_URI = os.getenv(
    'API_DB_WRITE_URI', 'postgresql+psycopg://postgres:LocalPassword@localhost:5432/notification_api'
)
