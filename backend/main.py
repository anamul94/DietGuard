from src.presentation.api.routes import socket_app

# Expose the app for uvicorn
app = socket_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)