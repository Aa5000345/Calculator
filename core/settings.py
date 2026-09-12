import json
import os
import copy


class Settings:
    def __init__(self, default_path):
        self.default_path = default_path
        self.user_dir = os.path.join(os.path.expanduser("~"), ".multicalc")
        os.makedirs(self.user_dir, exist_ok=True)
        self.user_path = os.path.join(self.user_dir, "settings.json")

        with open(default_path, "r", encoding="utf-8") as f:
            self.default = json.load(f)

        self.data = copy.deepcopy(self.default)
        if os.path.exists(self.user_path):
            try:
                with open(self.user_path, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except Exception:
                pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        with open(self.user_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)