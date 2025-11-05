

def get_order_delivery_tries_key(order_id):
    """
    Generates a key for tracking the number of delivery attempts for a specific order.
    Args:
        order_id (str or int): The unique identifier for the order.
    Returns:
        str: A formatted string representing the key for the order's delivery attempts.
    """
    
    return f"order:{order_id}:d_tries"

