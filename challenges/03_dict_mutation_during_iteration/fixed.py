"""Inventory cleanup — FIXED: iterates over a copy."""

def remove_out_of_stock(inventory: dict) -> dict:
    to_remove = [item for item, qty in inventory.items() if qty == 0]
    for item in to_remove:
        del inventory[item]
    return inventory
