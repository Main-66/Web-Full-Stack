# Web-Full-Stack

You know what to do.

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

## Step by Step

CMD 1

    cd C:\Users\**\**\**\*\Web-Full-Stack

    docker compose up -d

CMD 2

      cd C:\Users\**\**\**\*\Web-Full-Stack\backend

    python -m venv venv

    .\venv\Scripts\Activate.ps1

    pip install -r requirements.txt

    uvicorn app.main:app --reload --port 8000

CMD 3

    cd C:\Users\**\**\**\*\Web-Full-Stack\frontend

    npm install

    npm run dev