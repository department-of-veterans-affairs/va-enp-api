"""File for running the app locally with uvicorn. Simply run this file in debug mode to debug the app locally."""

import uvicorn
from dotenv import load_dotenv

if __name__ == '__main__':
    load_dotenv('.env.local')
    uvicorn.run('app.main:app', host='localhost', port=6012, reload=True)
