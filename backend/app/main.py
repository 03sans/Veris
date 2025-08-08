# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow the Vite dev server to talk to FastAPI during development
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # only allow the dev frontend
    allow_credentials=True,
    allow_methods=["*"],        # GET, POST, etc.
    allow_headers=["*"],        # Authorization, Content-Type, etc.
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Veris – Your AI Legal Assistant"}