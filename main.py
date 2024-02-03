import uvicorn
from fastapi import Request, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import argparse

from setup import init_async_functions
from realtime_status_logger import live_logger
from mq.handler import setup_to_frontend_template_data, MQ_HANDLER

from mq.api import router as process_manager_router
from realtime_status_logger import router as logger_router

PORT = 8000

# Setups a lifespan event handler, that can do stuff at startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    ''' Run at startup
        Initialise the Client and add it to app.state
    '''
    # Run any init code declared in setup.py
    await init_async_functions()

    yield
    ''' Run on shutdown
        Close the connection
        Clear variables and release the resources
    '''
    app.state.shutdown_handler()
    print("shutting down from lifespan")

app = FastAPI(lifespan=lifespan)

# Serve static files from the "static" directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create a Jinja2Templates instance and point it to the "templates" folder
templates = Jinja2Templates(directory="templates")

# Add routers to server api endpoints from other modules
app.include_router(logger_router)
app.include_router(process_manager_router)

# Set the channels that you want to log to throughout the app
live_logger.set_channels(["info", "error", "warning", "capacities", "gpt", "extra", "trash_emails"])

# Route for the root endpoint
@app.get("/")
async def read_root():
    live_logger.report_to_channel("info", "Hello from the root endpoint")
    return {"message": "Welcome to your FastAPI app!"}

@app.get("/info", response_class=HTMLResponse)
async def live_log(request: Request):

    # Provide data to be rendered in the template
    data = {
        "title": "Live Event Logging",
        "message": "Hello, FastAPI!",
        "user_id": live_logger.user_id,
        "channels": live_logger.channels,
        "buttons": setup_to_frontend_template_data(),
        "port": STARTUP_ARGS.port,
    }

    # Render the template with the provided data
    return templates.TemplateResponse("live_logger.html", {"request": request, **data})

def shutdown_handler():
    # Shut off any running producer/consumer tasks
    for tasks in MQ_HANDLER.values():
        tasks[1].set()
        print(f"set shutdown event for task {tasks[0].__name__}")

app.state.shutdown_handler = shutdown_handler

# Additional arguments to run the Uvicorn server
parser = argparse.ArgumentParser()

# Port to run server on, default is 8000
parser.add_argument("--port", type=int, default=8000, help="port to run server on")
# Server will auto reload if --reload is passed. Default is False
parser.add_argument("--reload", action="store_true", help="auto reload server on change")

STARTUP_ARGS = parser.parse_args() # If this is needed in other modules, import it from main.py

if __name__ == "__main__":
    # Simply type python main.py in terminal to run the server.
    # Additional arguments can be passed, check STARTUP_ARGS for details

    uvicorn.run("main:app", host="0.0.0.0", port=STARTUP_ARGS.port, reload=STARTUP_ARGS.reload)