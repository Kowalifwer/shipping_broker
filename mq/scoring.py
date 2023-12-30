from db import MongoCargo, MongoShip

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
            score += 1

        # SHIP GREAT
        if cargo.quantity_max_int * 1.10 >= ship.capacity_int >= cargo.quantity_max_int * 0.95:
            score += 2
        
        # SHIP TOO BIG
        if ship.capacity_int > cargo.quantity_max_int * 1.5:
            score -= 2
        
        if ship.capacity_int > cargo.quantity_max_int * 2:
            score -= 5
        
    return score

def month_modifier(ship: MongoShip, cargo: MongoCargo) -> float:
    score = 0
    """Modify score based on ship month vs cargo month logic."""
    if ship.month and cargo.month:
        if ship.month == cargo.month:
            score += 2
        elif abs(int(ship.month) - int(cargo.month)) == 1:
            score += 0.75
        else:
            score -= 1

    return score 