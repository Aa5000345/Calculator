"""设置管理：默认值 + 用户覆盖 + 热重载通知"""
import copy
import json
import os


class Settings:
    def __init__(self, default_path):
        self.default_path = default_path
        self.user_dir = os.path.join(os.path.expanduser("~"), ".multicalc")
        os.makedirs(self.user_dir, exist_ok=True)
        self.user_path = os.path.join(self.user_dir, "settings.json")

        with open(default_path, "r", encoding="utf-8") as f:
            self.default = json.load(f)

        self.data = copy.deepcopy(self.default)
        self._load_user()

        self._listeners = []

    # ---------------- 读写 ----------------

    def _load_user(self):
        if not os.path.exists(self.user_path):
            return
        try:
            with open(self.user_path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except Exception:
            pass

    def reload_if_changed(self) -> bool:
        """外部修改文件时调用；若内容变化则重新载入并返回 True。"""
        try:
            with open(self.user_path, "r", encoding="utf-8") as f:
                disk = json.load(f)
        except Exception:
            return False
        if disk == self.data:
            return False
        merged = copy.deepcopy(self.default)
        merged.update(disk)
        self.data = merged
        return True

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, notify=True):
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self.save()
        if notify:
            self._notify(key)

    def update(self, mapping, notify=True):
        changed = False
        for k, v in mapping.items():
            if self.data.get(k) != v:
                self.data[k] = v
                changed = True
        if not changed:
            return
        self.save()
        if notify:
            self._notify(None)

    def save(self):
        try:
            with open(self.user_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def reset(self, notify=True):
        self.data = copy.deepcopy(self.default)
        self.save()
        if notify:
            self._notify(None)

    # ---------------- 监听器 ----------------

    def add_listener(self, fn):
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_listener(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _notify(self, key=None):
        for fn in list(self._listeners):
            try:
                fn(key)
            except Exception:
                pass
