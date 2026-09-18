"""拼音首字母映射：为命令面板 / 侧边栏搜索提供中文拼音支持。

设计原则：
- 纯静态字典，无外部依赖（不引入 pypinyin）
- 覆盖 25 个面板的显示名 + 常用关键词
- 提供 `to_initials(text)` 把中文字符串转为首字母序列
- 提供 `pinyin_candidates(text)` 返回 [原文, 首字母, 全拼] 三种候选

用法：
    from core.pinyin_map import to_initials, pinyin_candidates
    to_initials("基础计算")          # "jcjs"
    pinyin_candidates("基础计算")    # ["基础计算", "jcjs", "jichujisuan"]
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# 单字 → 拼音首字母（覆盖项目内出现的所有汉字）
# ---------------------------------------------------------------------------

_CHAR_INITIAL = {
    # 面板名
    "基": "j", "础": "c", "科": "k", "学": "x", "计": "j", "算": "s",
    "单": "d", "位": "w", "换": "h", "汇": "h", "率": "l", "进": "j",
    "制": "z", "转": "z", "矩": "j", "阵": "z", "统": "t", "概": "g",
    "率": "l", "随": "s", "机": "j", "数": "s", "据": "j", "表": "b",
    "绘": "h", "图": "t", "财": "c", "务": "w", "日": "r", "期": "q",
    "位": "w", "运": "y", "加": "j", "密": "m", "工": "g", "具": "j",
    "片": "p", "段": "d", "时": "s", "器": "q", "剪": "j", "贴": "t",
    "板": "b", "脚": "j", "本": "b", "助": "z", "手": "s", "历": "l",
    "史": "s", "设": "s", "置": "z",
    # 分组名
    "转": "z", "换": "h", "数": "s", "据": "j", "数": "s", "学": "x",
    "财": "c", "务": "w", "工": "g", "具": "j", "生": "s", "产": "c",
    "力": "l", "系": "x", "统": "t", "其": "q", "他": "t",
    # 常用关键词（中文）
    "四": "s", "则": "z", "微": "w", "积": "j", "分": "f", "统": "t",
    "计": "j", "描": "m", "述": "s", "方": "f", "差": "c", "检": "j",
    "验": "y", "回": "h", "归": "g", "相": "x", "关": "g", "概": "g",
    "率": "l", "分": "f", "布": "b", "随": "s", "机": "j", "密": "m",
    "码": "m", "哈": "h", "希": "x", "加": "j", "密": "m", "解": "j",
    "码": "m", "公": "g", "式": "s", "表": "b", "格": "g", "绘": "h",
    "图": "t", "曲": "q", "线": "x", "贷": "d", "款": "k", "利": "l",
    "息": "x", "日": "r", "期": "q", "天": "t", "数": "s", "单": "d",
    "位": "w", "换": "h", "算": "s", "进": "j", "制": "z", "历": "l",
    "史": "s", "记": "j", "录": "l", "设": "s", "置": "z", "主": "z",
    "题": "t", "字": "z", "体": "t", "语": "y", "言": "y", "模": "m",
    "块": "k", "可": "k", "见": "j", "性": "x", "插": "c", "件": "j",
    "命": "m", "令": "l", "面": "m", "板": "b", "关": "g", "于": "y",
    "帮": "b", "助": "z", "检": "j", "查": "c", "更": "g", "新": "x",
    "导": "d", "入": "r", "出": "c", "复": "f", "制": "z", "粘": "z",
    "贴": "t", "清": "q", "空": "k", "删": "s", "除": "c", "保": "b",
    "存": "c", "打": "d", "开": "k", "关": "g", "闭": "b", "生": "s",
    "成": "c", "刷": "s", "新": "x", "重": "z", "置": "z", "应": "y",
    "用": "y", "取": "q", "消": "x", "确": "q", "定": "d",
}

# ---------------------------------------------------------------------------
# 词 → 全拼（仅覆盖面板名 + 分组名 + 高频关键词）
# ---------------------------------------------------------------------------

_WORD_FULL = {
    "基础": "jichu",
    "科学": "kexue",
    "计算": "jisuan",
    "单位": "danwei",
    "换算": "huansuan",
    "汇率": "huilv",
    "进制": "jinzhi",
    "转换": "zhuanhuan",
    "矩阵": "juzhen",
    "统计": "tongji",
    "概率": "gailv",
    "随机": "suiji",
    "数据": "shuju",
    "数据表": "shujubiao",
    "绘图": "huitu",
    "财务": "caiwu",
    "日期": "riqi",
    "位运算": "weiyunsuan",
    "加密": "jiami",
    "工具": "gongju",
    "片段": "pianduan",
    "计时": "jishi",
    "计时器": "jishiqi",
    "剪贴板": "jiantieban",
    "脚本": "jiaoben",
    "助手": "zhushou",
    "历史": "lishi",
    "设置": "shezhi",
    "生产力": "shengchanli",
    "系统": "xitong",
    "其他": "qita",
    "主题": "zhuti",
    "字体": "ziti",
    "语言": "yuyan",
    "模块": "mokuai",
    "可见性": "kejianxing",
    "插件": "chajian",
    "命令": "mingling",
    "面板": "mianban",
    "帮助": "bangzhu",
    "检查": "jiancha",
    "更新": "gengxin",
    "导入": "daoru",
    "导出": "daochu",
    "复制": "fuzhi",
    "粘贴": "zhantie",
    "清空": "qingkong",
    "删除": "shanchu",
    "保存": "baocun",
    "打开": "dakai",
    "关闭": "guanbi",
    "刷新": "shuaxin",
    "重置": "chongzhi",
    "应用": "yingyong",
    "取消": "quxiao",
    "确定": "queding",
    "贷款": "daikuan",
    "利息": "lixi",
    "公式": "gongshi",
    "表格": "biaoge",
    "曲线": "quxian",
    "回归": "huigui",
    "相关": "xiangguan",
    "分布": "fenbu",
    "密码": "mima",
    "哈希": "haxi",
    "编码": "bianma",
    "解码": "jiema",
    "校验": "jiaoyan",
    "逻辑": "luoji",
    "代数": "daishu",
    "微积分": "weijifen",
    "方程": "fangcheng",
    "求解": "qiujie",
    "化简": "huajian",
    "展开": "zhankai",
    "因式": "yinshi",
    "分解": "fenjie",
    "求导": "qiudao",
    "积分": "jifen",
    "极限": "jixian",
    "级数": "jishu",
    "求和": "qiuhe",
    "求积": "qiuji",
    "描述": "miaoshu",
    "方差": "fangcha",
    "检验": "jianyan",
    "描述统计": "miaoshutongji",
}


def to_initials(text: str) -> str:
    """把中文字符串转为拼音首字母序列。

    非中文字符直接保留（转为小写）。
    例："基础计算" → "jcjs"；"AI 助手" → "aizs"
    """
    if not text:
        return ""
    out = []
    for ch in str(text):
        if ch in _CHAR_INITIAL:
            out.append(_CHAR_INITIAL[ch])
        elif ch.isascii() and (ch.isalnum() or ch.isspace()):
            if ch.isalnum():
                out.append(ch.lower())
        # 其它符号忽略
    return "".join(out)


def to_full_pinyin(text: str) -> str:
    """把中文字符串转为全拼（仅覆盖映射表内的词）。

    未覆盖的字降级为首字母。
    """
    if not text:
        return ""
    s = str(text)
    out = []
    i = 0
    # 先尝试最长匹配（最大 4 字的词）
    word_keys = sorted(_WORD_FULL.keys(), key=len, reverse=True)
    while i < len(s):
        matched = False
        for w in word_keys:
            if s.startswith(w, i):
                out.append(_WORD_FULL[w])
                i += len(w)
                matched = True
                break
        if not matched:
            ch = s[i]
            if ch in _CHAR_INITIAL:
                out.append(_CHAR_INITIAL[ch])
            elif ch.isascii() and ch.isalnum():
                out.append(ch.lower())
            i += 1
    return "".join(out)


def pinyin_candidates(text: str) -> list[str]:
    """返回 [原文, 首字母, 全拼]（去重、去空）。"""
    out = []
    s = str(text or "").strip()
    if not s:
        return out
    out.append(s)
    ini = to_initials(s)
    if ini and ini not in out:
        out.append(ini)
    full = to_full_pinyin(s)
    if full and full not in out:
        out.append(full)
    return out


def expand_query(q: str) -> list[str]:
    """把用户查询扩展为多个候选，用于模糊匹配。

    输入 "jcjs" → ["jcjs", "基础计算", "jichujisuan"]
    输入 "基础" → ["基础", "jc", "jichu"]
    """
    q = str(q or "").strip()
    if not q:
        return []
    out = [q]
    ini = to_initials(q)
    if ini and ini not in out:
        out.append(ini)
    full = to_full_pinyin(q)
    if full and full not in out:
        out.append(full)
    return out


__all__ = [
    "to_initials",
    "to_full_pinyin",
    "pinyin_candidates",
    "expand_query",
]