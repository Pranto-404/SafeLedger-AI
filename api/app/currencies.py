"""ISO 4217 accounting currencies; no exchange-rate conversion."""
import json
from pathlib import Path
CURRENCIES = {x['code']:x for x in json.loads(Path(__file__).with_name('currencies.json').read_text())}
def scale(code):
    return 10 ** CURRENCIES[code]['digits']
