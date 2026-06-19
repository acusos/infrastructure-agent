import requests
import uuid

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION = "infra_memory"


def ensure_collection():

    requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION}",
        json={
            "vectors": {
                "size": 384,
                "distance": "Cosine"
            }
        }
    )


def save_note(text):

    point_id = str(uuid.uuid4())

    payload = {
        "points": [
            {
                "id": point_id,
                "vector": [0.0] * 384,
                "payload": {
                    "text": text
                }
            }
        ]
    }

    requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        json=payload
    )

    return point_id
