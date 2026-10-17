"""Generate precise, labelled wiring illustrations from the current V3 pin map.

These are logical connection drawings, not photographs or header orientation maps.
Run with a Python environment containing Pillow on Windows.
"""
from pathlib import Path
from html import escape
import json
import math

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
SCALE = 2
INK = "#172A42"
MUTED = "#58687C"
EDGE = "#D8E1EB"
RED = "#D64C43"
GND = "#3D4958"
SCL = "#B5810D"
SDA = "#008B84"
BLUE = "#3073C7"
CYAN = "#13849C"
PURPLE = "#8852BF"
ORANGE = "#C97022"
GREEN = "#27865D"
GREY = "#8995A3"


class Canvas:
    def __init__(self, width, height, title):
        self.width, self.height = width, height
        self.image = Image.new("RGB", (width * SCALE, height * SCALE), "#F4F7FB")
        self.draw = ImageDraw.Draw(self.image)
        self.svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            f'<title>{escape(title)}</title>',
            '<desc>按 visual_aid_v3 当前工程分配及 PYNQ-Z2 厂家手册绘制。逻辑连线图，非实物针脚方位图。</desc>',
            f'<rect width="{width}" height="{height}" fill="#F4F7FB"/>',
        ]

    def font(self, size, bold=False):
        return ImageFont.truetype(
            "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
            size * SCALE,
        )

    def text(self, x, y, value, size=28, color=INK, bold=False):
        self.draw.text((x * SCALE, y * SCALE), value, font=self.font(size, bold), fill=color, anchor="lt")
        self.svg.append(
            f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" '
            f'font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="{size}" '
            f'font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>'
        )

    def rect(self, x1, y1, x2, y2, fill="white", stroke=EDGE, radius=18, width=2):
        box = tuple(v * SCALE for v in (x1, y1, x2, y2))
        self.draw.rounded_rectangle(box, radius=radius * SCALE, fill=fill, outline=stroke, width=width * SCALE)
        self.svg.append(
            f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )

    def line(self, points, color=INK, width=5, dashed=False):
        if dashed:
            for a, b in zip(points, points[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                for n in range(0, int(length), 16):
                    t1, t2 = n / length, min(n + 9, length) / length
                    self.draw.line(
                        [((a[0] + dx*t1)*SCALE, (a[1] + dy*t1)*SCALE),
                         ((a[0] + dx*t2)*SCALE, (a[1] + dy*t2)*SCALE)],
                        fill=color, width=width*SCALE,
                    )
        else:
            self.draw.line([(x*SCALE, y*SCALE) for x, y in points], fill=color, width=width*SCALE, joint="curve")
        pts = " ".join(f"{x},{y}" for x, y in points)
        dash = ' stroke-dasharray="9 7"' if dashed else ""
        self.svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{dash}/>')

    def dot(self, x, y, color=INK, radius=8, fill=None):
        fill = fill or color
        self.draw.ellipse(((x-radius)*SCALE, (y-radius)*SCALE, (x+radius)*SCALE, (y+radius)*SCALE), fill=fill, outline=color, width=2*SCALE)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="{color}" stroke-width="2"/>')

    def wire(self, y, color, source, port, target, target_note=""):
        self.text(112, y-18, source, 29, color, True)
        self.text(298, y-16, port, 25, MUTED)
        self.line([(610, y), (1025, y)], color, 6)
        self.dot(610, y, color, 9, "white")
        self.dot(1025, y, color, 9, "white")
        self.text(1055, y-28, target, 29, color, True)
        if target_note:
            self.text(1210, y-15, target_note, 25, MUTED)

    def save(self, name):
        self.image.save(OUT / f"{name}.png", optimize=True)
        (OUT / f"{name}.svg").write_text("\n".join(self.svg + ["</svg>"]), encoding="utf-8")


def check_project_pins():
    pins = json.loads((OUT.parent / "pins.json").read_text(encoding="utf-8-sig"))
    expected = {"sensor_sda": "P16", "sensor_scl": "P15",
                "joy_n[0]": "V13", "joy_n[1]": "V15", "joy_n[2]": "T15",
                "joy_n[3]": "R16", "joy_n[4]": "U17"}
    for signal, pin in expected.items():
        if pins[signal] != pin:
            raise ValueError(f"Diagram pin map is stale: {signal}: {pins[signal]} != {pin}")


def sensor():
    c = Canvas(1600, 940, "GY-302 / BH1750 光照传感器接线图")
    c.text(64, 38, "① 光照传感器接线图", 43, bold=True)
    c.text(66, 101, "GY-302 / BH1750  →  PYNQ-Z2 的 Arduino 接口", 27, MUTED)
    c.rect(48, 160, 1552, 700)
    c.rect(78, 231, 630, 668, "#F8FAFD")
    c.rect(1000, 231, 1520, 668, "#EEF8F6", "#C7E1DC")
    c.text(109, 184, "PYNQ-Z2 开发板", 31, bold=True)
    c.text(1028, 184, "GY-302 光照模块", 31, bold=True)
    c.text(111, 258, "板上丝印", 22, MUTED)
    c.text(298, 258, "接口与脚号", 22, MUTED)
    c.text(1055, 258, "按模块丝印接线", 22, MUTED)

    c.wire(337, RED, "3V3", "J7 第 5 脚", "VCC / VIN")
    c.wire(402, GND, "GND", "J7 第 2 脚", "GND")
    c.wire(467, SCL, "SCL", "J3 第 10 脚", "SCL")
    c.wire(532, SDA, "SDA", "J3 第 9 脚", "SDA")
    # A spare board GND pin avoids putting two jumper wires on one module pin.
    c.wire(605, GND, "GND", "J3 第 7 脚", "ADDR", "地址 0x23")
    c.text(669, 365, "含 ADDR 接地，共五根线", 22, MUTED)

    c.rect(48, 723, 1552, 862, "#FFF8EB", "#EAD6AC")
    c.text(77, 745, "供电条件：本图适用于允许 3.3 V 输入的 GY-302 模块。", 27, "#805818", True)
    c.text(77, 794, "你提供的模块带稳压器；3.3 V 输入时，需确认芯片端供电仍为 2.4～3.6 V。", 25, "#805818")
    c.text(65, 887, "断电接线，按丝印找脚。此图为逻辑连线，不表示实物接口的朝向与排列。", 25, MUTED)
    c.save("01_bh1750_wiring")
    return c.image


def keys():
    c = Canvas(1600, 1090, "八针五向导航按键接线图")
    c.text(64, 38, "② 五向导航按键接线图", 43, bold=True)
    c.text(66, 101, "适用于你提供的 COM / UP / DWN / LFT / RHT / MID / SET / RST 八针模块", 26, MUTED)
    c.rect(48, 160, 1552, 896)
    c.rect(78, 231, 630, 715, "#F8FAFD")
    c.rect(1000, 231, 1520, 864, "#F3F1FA", "#DCD3ED")
    c.text(109, 184, "同一块 PYNQ-Z2 开发板", 31, bold=True)
    c.text(1028, 184, "八针五向按键模块", 31, bold=True)
    c.text(111, 258, "板上丝印", 22, MUTED)
    c.text(298, 258, "接口与脚号", 22, MUTED)
    c.text(1055, 258, "模块丝印", 22, MUTED)
    c.text(1225, 258, "当前工程功能", 22, MUTED)
    c.wire(323, GND, "GND", "J7 第 3 脚", "COM", "公共端")
    c.wire(393, BLUE, "D3", "J4 第 4 脚", "UP", "向上移动")
    c.wire(463, CYAN, "D4", "J4 第 5 脚", "DWN", "向下移动")
    c.wire(533, PURPLE, "D5", "J4 第 6 脚", "LFT", "向左移动")
    c.wire(603, ORANGE, "D6", "J4 第 7 脚", "RHT", "向右移动")
    c.wire(673, GREEN, "D7", "J4 第 8 脚", "MID", "1× / 2× / 4×")
    for y, name in [(753, "SET"), (823, "RST")]:
        c.line([(936, y), (1025, y)], GREY, 4, True)
        c.dot(1025, y, GREY, 8, "white")
        c.line([(925, y-10), (945, y+10)], GREY, 3)
        c.line([(925, y+10), (945, y-10)], GREY, 3)
        c.text(1055, y-19, name, 29, GREY, True)
        c.text(1210, y-15, "留空，不接", 25, GREY)
    c.text(111, 755, "只接 COM 与五路按键信号，共六根线。", 26, bold=True)
    c.text(111, 804, "J7 的两个 GND 在开发板内部相通。", 25, MUTED)

    c.rect(48, 918, 1552, 1018, "#EDF4FE", "#C7D9F4")
    c.text(77, 938, "COM 接地，无源按键不接 3.3 V / 5 V；RST 不接开发板的复位接口。", 27, INK, True)
    c.text(77, 979, "D3～D7 指 Arduino 接口丝印；工程已启用内部上拉，按下为低电平。", 24, MUTED)
    c.text(65, 1043, "断电接线。J4 第 4 脚与 40 针接口第 4 脚不同；本图不是实物针脚方位图。", 25, MUTED)
    c.save("02_five_way_wiring")
    return c.image


def main():
    check_project_pins()
    first = sensor()
    second = keys()
    combined = Image.new("RGB", (first.width, first.height + second.height), "white")
    combined.paste(first, (0, 0))
    combined.paste(second, (0, first.height))
    combined.save(OUT / "bh1750_and_five_way_wiring.png", optimize=True)
    print("Created BH1750 and five-way wiring PNG/SVG illustrations.")


if __name__ == "__main__":
    main()
