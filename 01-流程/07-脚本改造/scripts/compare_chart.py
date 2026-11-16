# -*- coding: utf-8 -*-
"""改前 / 改后分镜对照图生成器。

用法:
    python compare_chart.py spec.json out.png

依赖: Python 3.6+、Pillow 8.2+、系统内任意一款中文字体。
缺依赖或字体时会直接给出可照做的安装提示，不会抛裸 traceback。

spec.json 结构:
{
  "title":    "《xxx》改前 / 改后 分镜对照",
  "subtitle": "同一时间刻度：色块长度就是镜头时长，总高就是片长",
  "left":  {"label": "改前 · 45 秒 · 10 镜", "accent": "#A32D2D",
            "shots": [{"dur": 3, "label": "1  爆油特写", "kind": "ok"}, ...]},
  "right": {"label": "改后 · 33 秒 · 9 镜", "accent": "#185FA5",
            "shots": [...], "marked": [3,4,5], "mark_text": "13 秒在说同一件事"},
  "footer": {"big": "45 秒 → 33 秒", "stats": "改 5 镜 · 删 4 镜 · 留 1 镜 · 增 3 镜"}
}

kind 取值: ok(有效但普通) / bad(空转) / amber(证据位) / blue(改后新结构)
marked 为可选，指定左侧需要竖括号标注的镜头序号（1-based 连续区间）。
mark_text 建议不超过 12 字；超出会自动缩字号，缩到下限仍放不下则截断加省略号。
footer.big 与 stats 顺序自动排布，空间不够时图例自动换行。

注意：色块高度 = 时长 × 17.5px，但**不足 26px 的短镜按下限 26px 画**（否则
0.5–1.5 秒的镜头放不下标签）。也就是说短镜的高度不完全等于时长比例，长镜不受影响。
"""
import json
import os
import sys

MIN_PILLOW = (8, 2)


def load_pillow():
    """缺 Pillow、版本过低、安装损坏，各给各的提示，别让用户对着一行 AttributeError 猜。"""
    try:
        import PIL
    except ImportError:
        raise SystemExit(
            "缺少 Pillow，无法生成对照图。安装后重试：\n"
            "    pip install -U pillow"
        )
    version = getattr(PIL, "__version__", "0")
    try:
        parts = tuple(int(p) for p in version.split(".")[:2])
    except ValueError:
        parts = (0, 0)
    if parts < MIN_PILLOW:
        raise SystemExit(
            f"Pillow {version} 版本过低，需要 {MIN_PILLOW[0]}.{MIN_PILLOW[1]} 以上"
            "（rounded_rectangle 自 8.2 起提供）。\n"
            "升级后重试：pip install -U pillow"
        )
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit(
            f"Pillow 已安装但导入失败：{exc}\n"
            "多为安装损坏、或 _imaging 扩展与 PIL 版本不一致，重装可修复：\n"
            "    pip install --force-reinstall pillow"
        )
    return Image, ImageDraw, ImageFont


Image, ImageDraw, ImageFont = load_pillow()

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"),
    ("C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"),
    ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
     "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
]

# 候选路径全落空时，扫这些目录里文件名像中文字体的文件
FONT_DIRS = [
    "C:/Windows/Fonts",
    "/System/Library/Fonts",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
]
CJK_HINTS = ("cjk", "noto", "hei", "song", "ming", "kai", "yahei",
             "pingfang", "sourcehan", "wqy", "droidsansfallback")

STYLE = {
    "ok":    ("#F2F0E9", "#C9C6BB", "#3A3A36"),
    "bad":   ("#FBE4E3", "#E24B4A", "#7A2221"),
    "amber": ("#FCEEDA", "#BA7517", "#6B420B"),
    "blue":  ("#E3EFFC", "#378ADD", "#0D3E6E"),
}

SCALE = 17.5      # 每秒像素
MIN_BLOCK_H = 26  # 短镜渲染高度下限：1s 按比例只有 17.5px，扣掉间隙放不下标签
PANEL_W = 700
LEFT_X = 60
GAP = 100
TOP = 190


def has_cjk(path):
    """能加载不等于有中文字形：真渲染一个汉字，有字形宽度才认。"""
    try:
        font = ImageFont.truetype(path, 20)
        box = font.getbbox("中")
    except Exception:
        return False
    return bool(box) and box[2] > 0 and box[3] > 0


def scan_fonts():
    for root in FONT_DIRS:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for name in sorted(files):
                low = name.lower()
                if not low.endswith((".ttf", ".ttc", ".otf")):
                    continue
                if not any(h in low for h in CJK_HINTS):
                    continue
                path = os.path.join(dirpath, name)
                if has_cjk(path):
                    return path
    return None


def pick_fonts():
    for bold, regular in FONT_CANDIDATES:
        bold_ok, regular_ok = has_cjk(bold), has_cjk(regular)
        if bold_ok and regular_ok:
            return bold, regular
        if regular_ok:
            return regular, regular      # 只有常规体时，粗体降级为常规
    found = scan_fonts()
    if found:
        return found, found
    raise SystemExit(
        "找不到任何可用的中文字体，无法生成对照图。\n"
        "装一款中文字体后重试：\n"
        "    Ubuntu / Debian : sudo apt install fonts-noto-cjk\n"
        "    CentOS / RHEL   : sudo yum install google-noto-sans-cjk-fonts\n"
        "    Alpine          : apk add font-noto-cjk\n"
        "    macOS / Windows : 系统自带中文字体，若被精简请手动安装\n"
        "也可以把字体路径填进本文件的 FONT_CANDIDATES。"
    )


BOLD, REGULAR = pick_fonts()


def f(bold, size):
    return ImageFont.truetype(BOLD if bold else REGULAR, size)


def block_h(dur):
    """色块高度 = 时长 × SCALE；不足 MIN_BLOCK_H 的按下限画，否则标签放不下。"""
    return max(dur * SCALE, MIN_BLOCK_H)


def panel_height(shots):
    return sum(block_h(s["dur"]) for s in shots)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("用法: python compare_chart.py spec.json out.png")
        print()
        print("spec.json 结构见本文件顶部 docstring；依赖 Pillow 与一款中文字体。")
        return 0
    if len(sys.argv) < 3:
        raise SystemExit("用法: python compare_chart.py spec.json out.png")

    out = sys.argv[2]
    out_dir = os.path.dirname(os.path.abspath(out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    left, right = spec["left"], spec["right"]

    body = max(panel_height(left["shots"]), panel_height(right["shots"]))
    height = int(TOP + body + 190)
    img = Image.new("RGB", (1600, height), "#FFFFFF")
    d = ImageDraw.Draw(img)

    d.text((60, 34), spec.get("title", ""), font=f(True, 34), fill="#1F1F1D")
    if spec.get("subtitle"):
        d.text((60, 86), spec["subtitle"], font=f(False, 18), fill="#9A9892")

    right_x = LEFT_X + PANEL_W + GAP
    d.text((LEFT_X, TOP - 44), left["label"], font=f(True, 23),
           fill=left.get("accent", "#A32D2D"))
    d.text((right_x, TOP - 44), right["label"], font=f(True, 23),
           fill=right.get("accent", "#185FA5"))

    def draw(x, shots):
        y = TOP
        for s in shots:
            h = block_h(s["dur"])
            usable = h - 6
            fill, stroke, ink = STYLE.get(s.get("kind", "ok"), STYLE["ok"])
            d.rounded_rectangle([x, y, x + PANEL_W, y + usable], radius=9,
                                fill=fill, outline=stroke, width=2)
            # 短镜的块高被 MIN_BLOCK_H 抬到 26px 后，21px 的字仍会压边，字号随块高收缩。
            fs = max(11, min(21, int(usable / 1.9)))
            cy = y + usable / 2
            d.text((x + 24, cy), s["label"], font=f(False, fs), fill=ink, anchor="lm")
            fs2 = max(10, fs - 4)
            tw = d.textlength(f"{s['dur']}s", font=f(False, fs2))
            d.text((x + PANEL_W - 24 - tw, cy), f"{s['dur']}s",
                   font=f(False, fs2), fill=ink, anchor="lm")
            y += h
        return y

    ly = draw(LEFT_X, left["shots"])
    draw(right_x, right["shots"])

    marked = left.get("marked")
    if marked and len(marked) >= 2:
        start = TOP + sum(block_h(s["dur"]) for s in left["shots"][:marked[0] - 1])
        end = TOP + sum(block_h(s["dur"]) for s in left["shots"][:marked[-1]])
        bx = LEFT_X + PANEL_W + 16
        d.line([(bx, start + 4), (bx, end - 6)], fill="#E24B4A", width=3)
        d.line([(bx, start + 4), (bx + 12, start + 4)], fill="#E24B4A", width=3)
        d.line([(bx, end - 6), (bx + 12, end - 6)], fill="#E24B4A", width=3)

        text = left.get("mark_text", "")
        if text:
            size = 20
            avail = int(end - start) - 10
            tw = int(d.textlength(text, font=f(True, size)))
            if avail > 0 and tw > avail:
                size = max(13, int(size * avail / tw))
                tw = int(d.textlength(text, font=f(True, size)))
            if avail > 0 and tw > avail:
                keep = max(2, int(len(text) * avail / tw) - 1)
                text = text[:keep] + "…"
                tw = int(d.textlength(text, font=f(True, size)))
            tmp = Image.new("RGBA", (tw + 6, 36), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).text((0, 0), text, font=f(True, size), fill="#C0392B")
            rot = tmp.rotate(90, expand=True)
            img.paste(rot, (bx + 28, int((start + end) / 2) - rot.height // 2), rot)

    by = int(max(ly, TOP + body) + 52)
    d.line([(60, by - 26), (1540, by - 26)], fill="#DEDBD2", width=2)
    footer = spec.get("footer", {})
    fx = 60
    if footer.get("big"):
        d.text((fx, by), footer["big"], font=f(True, 27), fill="#1F1F1D")
        fx += int(d.textlength(footer["big"], font=f(True, 27))) + 36
    if footer.get("stats"):
        d.text((fx, by + 8), footer["stats"], font=f(False, 20), fill="#6B6A66")
        fx += int(d.textlength(footer["stats"], font=f(False, 20)))

    legend = [("空转", "bad"), ("有效但普通", "ok"), ("证据位", "amber"), ("改后新结构", "blue")]
    lx, lyy = max(fx + 48, 905), by + 2
    for name, kind in legend:
        need = 29 + int(d.textlength(name, font=f(False, 18))) + 26
        if lx + need > 1540:
            lx, lyy = 60, lyy + 42
        fill, stroke, _ = STYLE[kind]
        d.rounded_rectangle([lx, lyy, lx + 20, lyy + 18], radius=3,
                            fill=fill, outline=stroke, width=2)
        d.text((lx + 29, lyy), name, font=f(False, 18), fill="#6B6A66")
        lx += need

    img.save(out)
    print(f"saved {out} {img.size}")


if __name__ == "__main__":
    sys.exit(main() or 0)
