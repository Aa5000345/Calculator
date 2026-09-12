import datetime
import json
import os


class History:
    def __init__(self):
        self.dir = os.path.join(os.path.expanduser("~"), ".multicalc")
        os.makedirs(self.dir, exist_ok=True)
        self.path = os.path.join(self.dir, "history.json")
        self.items = []

        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.items = json.load(f)
            except Exception:
                self.items = []

    def add(self, module, expr, result):
        self.items.append({
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "module": module,
            "expr": str(expr),
            "result": str(result),
        })
        self.save()

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.items[-2000:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def clear(self):
        self.items = []
        self.save()
