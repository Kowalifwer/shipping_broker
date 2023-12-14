from fastapi.routing import APIRouter
from fastapi import BackgroundTasks
from typing import Literal

from realtime_status_logger import live_logger
from mq.handler import MQ_HANDLER

router = APIRouter()

@router.get("/{action}/{task_type}/{name}")
async def launch_backgrond_task(background_tasks: BackgroundTasks, action: Literal["start", "end"], task_type: Literal["consumer", "producer"], name: str):
    if action not in ["start", "end"]:
        live_logger.report_to_channel("error", f"Invalid action {action}. Must be either 'start' or 'end'")
        return {"error": f"Invalid action {action}. Must be either 'start' or 'end'"}

    if task_type not in ["consumer", "producer"]:
        live_logger.report_to_channel("error", f"Invalid task type {task_type}. Must be either 'consumer' or 'producer'")
        return {"error": f"Invalid task type {task_type}. Must be either 'consumer' or 'producer'"}

    if name not in MQ_HANDLER:
        live_logger.report_to_channel("error", f"Invalid task name {name}. Must be one of {MQ_HANDLER.keys()}")
        return {"error": f"Invalid task name {name}. Must be one of {MQ_HANDLER.keys()}"}
    
    # Remove last word after underscore, and capitalize

    task_function = MQ_HANDLER[name][0]
    task_event = MQ_HANDLER[name][1]
    message_queue = MQ_HANDLER[name][2]
    remaining_args = MQ_HANDLER[name][3:]

    extra_params_temp = {}
    name_sections = name.split("_")
    ## check if last word is a number
    if name_sections[0].isnumeric():
        extra_params_temp["n"] = int(name_sections[0])

    if action == "start":
        task_event.clear()

        # background_tasks.add_task(task_function, task_event, message_queue)
        background_tasks.add_task(*MQ_HANDLER[name], **extra_params_temp)
    elif action == "end":
        task_event.set()
    
    name = " ".join(name.split("_")[:-1]).capitalize()

    live_logger.report_to_channel("info", f"Request to {action} '{task_type.capitalize()}' task '{name}' processed.")

    return {"message": f"Request to {action} '{task_type.capitalize()}' task '{name}' processed."}