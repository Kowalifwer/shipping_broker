import uvicorn
from fastapi import Request, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from realtime_status_logger import live_logger
from mq.handler import setup_to_frontend_template_data, MQ_HANDLER

from mq.api import router as process_manager_router
from realtime_status_logger import router as logger_router

# Setups a lifespan event handler, that can do stuff at startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    ''' Run at startup
        Initialise the Client and add it to app.state
    '''
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
        "buttons": setup_to_frontend_template_data()
    }

    # Render the template with the provided data
    return templates.TemplateResponse("live_logger.html", {"request": request, **data})

def shutdown_handler():
    # Shut off any running producer/consumer tasks
    for tasks in MQ_HANDLER.values():
        tasks[1].set()
        print(f"set shutdown event for task {tasks[0].__name__}")

app.state.shutdown_handler = shutdown_handler

if __name__ == "__main__":

    #uvicorn main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000, use_colors=True)
    # uvicorn.run(app)