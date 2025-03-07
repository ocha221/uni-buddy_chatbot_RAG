# api/server.py
import uvicorn
from api.routes import app

def start_server(host="0.0.0.0", port=8000):
    """Start the API server"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_server()