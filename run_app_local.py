"""File for running the app locally with uvicorn. Simply run this file in debug mode to debug the app locally."""

import uvicorn

if __name__ == '__main__':
    uvicorn.run('app.main:app', host='localhost', port=8000, reload=True)
