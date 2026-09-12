import json
import os


class I18n:
    def __init__(self, dir_path, lang="zh_CN"):
        self.dir = dir_path
        self.lang = lang
        self.trans = {}
        self.load(lang)

    def load(self, lang):
        path = os.path.join(self.dir, f"{lang}.json")
        if not os.path.exists(path):
            path = os.path.join(self.dir, "en_US.json")
            lang = "en_US"
        with open(path, "r", encoding="utf-8") as f:
            self.trans = json.load(f)
        self.lang = lang

    def t(self, key, default=None):
        return self.trans.get(key, default if default is not None else key)
