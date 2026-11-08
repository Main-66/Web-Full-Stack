# Web-Full-Stack

### You know what to do. 

if you use terminal:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

## How to run

**1. Database**
```bash
docker compose up -d
```

**2. Backend**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```

Open **`http://localhost:5173`** *(works offline even if Ollama isn't running)*.