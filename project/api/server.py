# api/server.py
import uvicorn
from api.routes import app


def start_server(host="0.0.0.0", port=8000, refresh_interval=12):
    """Start the API server"""
    uvicorn.run(app, host=host, port=port, refresh_interval=refresh_interval)


if __name__ == "__main__":
    start_server()
