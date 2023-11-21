from fastapi import FastAPI, HTTPException
import redis 
from models import ItemPayload

app = FastAPI()

redis_client = redis.StrictRedis(host='127.0.0.1', port=6379, db=0, decode_responses=True)

@app.get("/")
def root():
    return {"message": "Hello World"}

# Route to add a item
@app.post("/items/{item_name}/{quantity}")
def add_item(
    item_name: str, 
    quantity: int
    ) -> dict[str, ItemPayload]:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0.")
    # if item already exists, we'll just add the quantity.
    # get all item names
    item_id_str: str | None = redis_client.hget("item_name_to_id", item_name)

    if item_id_str is not None:
        # get index of item_name in item_ids, which is the item_id
        item_id = int(item_id_str)
        redis_client.hincrby(f"item_id:{item_id}", "quantity", quantity)
    # otherwise, create a new item
    else:
        # To generate a new item_id, let's use the incr method from Redis, passing a new hash called "item_ids". 
        # This hash is used to store the last generated ID, so we can increment it each time we create a new item, ensuring that they all have a unique ID.
        # When this incr call is run for the first time with the item_ids key, Redis creates the key and maps it to the value 1. 
        # Then, each subsequent time it's run, it increments the stored value by 1.
        item_id: int = redis_client.incr("item_ids")

        # add the item to the Redis hash, using the hset method and by providing a mapping for the fields (item_id, item_name, and quantity)
        redis_client.hset(
            f"item_id:{item_id}",
            mapping={
                "item_id": item_id,
                "item_name": item_name,
                "quantity": quantity,
            })
        
        # map the newly created ID to the item name by setting the hash item_name_to_id
        redis_client.hset("item_name_to_id", item_name, item_id)

    return {"item": ItemPayload(item_id=item_id, 
                                item_name=item_name, 
                                quantity=quantity)
                                }    

# Route to list a specific item by ID but using Redis
@app.get("/items/{item_id}")
def list_item(item_id: int) -> dict[str, dict[str, str]]:
    if not redis_client.hexists(f"item_id:{item_id}", "item_id"):
        raise HTTPException(status_code=404, detail="Item not found.")
    else:
        return {"item": redis_client.hgetall(f"item_id:{item_id}")}



# Route to list all items from Redis 
@app.get("/items")
def list_items() -> dict[str, list[ItemPayload]]:
    items: list[ItemPayload] = []
    stored_items: dict[str, str] = redis_client.hgetall("item_name_to_id")

    for name, id_str in stored_items.items():
        item_id: int = int(id_str)

        item_name_str: str | None = redis_client.hget(f"item_id:{item_id}", "item_name")
        if item_name_str is not None:
            item_name: str = item_name_str
        else:
            continue  # skip this item if it has no name

        item_quantity_str: str | None = redis_client.hget(
            f"item_id:{item_id}", "quantity"
        )
        if item_quantity_str is not None:
            item_quantity: int = int(item_quantity_str)
        else:
            item_quantity = 0

        items.append(
            ItemPayload(item_id=item_id, item_name=item_name, quantity=item_quantity)
        )

    return {"items": items}


# Route to delete a specific item by ID but using Redis
@app.delete("/items/{item_id}")
def delete_item(item_id: int) -> dict[str, str]:
    if not redis_client.hexists(f"item_id:{item_id}", "item_id"):
        raise HTTPException(status_code=404, detail="Item not found.")
    else:
        item_name: str | None = redis_client.hget(f"item_id:{item_id}", "item_name")
        redis_client.hdel("item_name_to_id", f"{item_name}")
        redis_client.delete(f"item_id:{item_id}")
        return {"result": f"Item ({item_id}, {item_name}) deleted."}


# Route to remove some quantity of a specific item by ID but using Redis
@app.delete("/items/{item_id}/{quantity}")
def remove_quantity(item_id: int, quantity: int) -> dict[str, str]:
    if not redis_client.hexists(f"item_id:{item_id}", "item_id"):
        raise HTTPException(status_code=404, detail="Item not found.")

    item_quantity: str | None = redis_client.hget(f"item_id:{item_id}", "quantity")
    item_name: str | None = redis_client.hget(f"item_id:{item_id}", "item_name")

    # if quantity to be removed is higher or equal to item's quantity, delete the item
    if item_quantity is None:
        existing_quantity: int = 0
    else:
        existing_quantity: int = int(item_quantity)
    if existing_quantity <= quantity:        
        redis_client.hdel("item_name_to_id", f"{item_name}")
        redis_client.delete(f"item_id:{item_id}")
        return {"result": f"Item ({item_id}, {item_name}) deleted."}
    else:
        redis_client.hincrby(f"item_id:{item_id}", "quantity", -quantity)
        return {"result": f"{quantity} of {existing_quantity} items from ({item_id}, {item_name}) removed."}
