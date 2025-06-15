import os, json

CONF_PATH = os.path.join(os.path.dirname(__file__), "arhouse.json")

def load():
    if not os.path.exists(CONF_PATH):
        return {}
    with open(CONF_PATH) as f:
        return json.load(f)

def save(cfg):
    os.makedirs(os.path.dirname(CONF_PATH), exist_ok=True)
    with open(CONF_PATH, "w") as f:
        json.dump(cfg, f)
