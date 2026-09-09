"""Inventory cleanup — BUGGY: modifies dict during iteration."""

def remove_out_of_stock(inventory: dict) -> dict:
    for item, qty in inventory.items():  # BUG: modifying dict during iteration
        if qty == 0:
            del inventory[item]
    return inventory
