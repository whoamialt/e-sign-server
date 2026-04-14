"""Start the e-sign web server."""
import uvicorn
from server.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run("server.app:app", host=HOST, port=PORT, reload=True)
