from typing import Iterable
from db import MongoCargo, MongoShip
import numpy as np

def capacity_modifier(ship: MongoShip, cargo: MongoCargo) -> float:
    score = 0
    """Modify score based on ship capacity vs cargo quantity logic."""
    if ship.capacity_int:
        if not (cargo.quantity_min_int and cargo.quantity_max_int):
            score -= 2
            return score # penalize the score if cargo quantity is not specified
        
        # SHIP TOO SMALL
        if ship.capacity_int < cargo.quantity_min_int * 0.90:
            score -= 5
            return score # heavily penalize the score if ship capacity is less than cargo lower bound

        # SHIP ACCEPTABLE
        if ship.capacity_int > cargo.quantity_min_int:
            score += 1
        
        # SHIP GOOD
        if ship.capacity_int > cargo.quantity_max_int * 0.85:
            score += 2

        # SHIP GREAT
        if cargo.quantity_max_int * 1.10 >= ship.capacity_int >= cargo.quantity_max_int * 0.95:
            score += 4
        
        # SHIP TOO BIG
        if ship.capacity_int > cargo.quantity_max_int * 1.5:
            score -= 2
        
        if ship.capacity_int > cargo.quantity_max_int * 2:
            score -= 5
        
    return score

def month_modifier(ship: MongoShip, cargo: MongoCargo) -> float:
    score = 0
    """Modify score based on ship month vs cargo month logic."""
    if not ship.month_int:
        return score

    if cargo.month_int:
        if ship.month_int == cargo.month_int:
            score += 3
        elif abs(ship.month_int - cargo.month_int) == 1:
            score += 0
        else:
            score -= 5
    else:
        score -= 2

    return score

def comission_modifier(ship: MongoShip, cargo: MongoCargo) -> float:
    score = 0
    """Modify score based on cargo comission logic."""
    if cargo.commission_float:
        if cargo.commission_float <= 1.25:
            score += 6
        elif cargo.commission_float <= 2.5:
            score += 3
        elif cargo.commission_float <= 3.75:
            score += 1
        elif cargo.commission_float <= 4:
            score += 0
        elif cargo.commission_float <= 5:
            score -= 1
        else: # >5 %
            score -= 6

    return score

def timestamp_created_modifier(ship: MongoShip, cargo: MongoCargo) -> float:
    score = 0
    """Modify score based on cargo date created logic."""
    if cargo.timestamp_created:
        # 1-3 days - big boost, 3-7 days small boost, 7-14 days small penalty, 14+ days big penalty
        days = (cargo.timestamp_created - ship.timestamp_created).days
        if days <= 3:
            score += 5
        elif days <= 7:
            score += 2
        elif days <= 14:
            score += 0
        elif days <= 30:
            score -= 2
        else:
            score -= 5

    return score

def min_max_scale_robust(data: Iterable, min_val=-0.1, max_val=1) -> np.ndarray:
    data = np.array(data)

    median = np.median(data)
    q25, q75 = np.percentile(data, [25, 75])
    iqr = q75 - q25
    scaled_data = (data - median) / iqr
    scaled_data = np.clip(scaled_data, -1.0, 1.0)
    scaled_data = 0.5 * (scaled_data + 1.0) * (max_val - min_val) + min_val
    return scaled_data