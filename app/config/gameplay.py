import json
from app.config.settings import resource_root

GAMEPLAY = json.loads((resource_root() / 'app/config/gameplay.json').read_text(encoding='utf-8'))
