"""Run against a live local backend, without writing financial state."""
import json
from urllib.request import urlopen
for route in ("health", "ready"):
    with urlopen("http://127.0.0.1:8000/api/" + route, timeout=5) as response:
        data = json.load(response)
        assert response.status == 200
        assert data["status"] == ("ok" if route == "health" else "ready")
        print(route + ": " + json.dumps(data, sort_keys=True))
