import json
import os


class I18n:
    def __init__(self, dir_path, lang="zh_CN"):
        self.dir = dir_path
        self.lang = lang
        self.trans = {}
        self.load(lang)

    def load(self, lang):
        self.lang = lang
        path = os.path.join(self.dir, f"{lang}.json")
        with open(path, "r", encoding="utf-8") as f:
            self.trans = json.load(f)

    def t(self, key, default=None):
        return self.trans.get(key, default or key)