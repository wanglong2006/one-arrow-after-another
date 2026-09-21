"""一箭又一箭：使用 Python 标准库 Tkinter 实现的单机小游戏。

运行方式：python one_arrow_after_another.py
"""

from __future__ import annotations

import json
import math
import os
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


Direction = str
ArrowMap = dict[tuple[int, int], Direction]

DIRECTION_VECTORS: dict[Direction, tuple[int, int]] = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}


def path_is_clear(
    arrows: ArrowMap, row: int, col: int, direction: Direction, grid_size: int
) -> bool:
    """判断指定箭头到棋盘边界之间是否没有其他箭头。"""
    dr, dc = DIRECTION_VECTORS[direction]
    row, col = row + dr, col + dc
    while 0 <= row < grid_size and 0 <= col < grid_size:
        if (row, col) in arrows:
            return False
        row, col = row + dr, col + dc
    return True


def find_solution(arrows: ArrowMap, grid_size: int) -> list[tuple[int, int]] | None:
    """寻找一条完整通关顺序；无解时返回 None。

    消除箭头只会减少阻挡、不会产生新阻挡，因此每轮任选一个当前可飞出的
    箭头都是安全的；若某轮仍有箭头却没有合法选择，剩余局面必然无解。
    """
    remaining = dict(arrows)
    order: list[tuple[int, int]] = []
    while remaining:
        move = next(
            (
                position
                for position in sorted(remaining)
                if path_is_clear(
                    remaining,
                    position[0],
                    position[1],
                    remaining[position],
                    grid_size,
                )
            ),
            None,
        )
        if move is None:
            return None
        order.append(move)
        del remaining[move]
    return order


@dataclass(frozen=True)
class Level:
    name: str
    size: int
    mistakes: int
    arrows: tuple[tuple[int, int, Direction], ...]
    subtitle: str

    def arrow_map(self) -> ArrowMap:
        return {(row, col): direction for row, col, direction in self.arrows}


LEVELS = (
    Level(
        "初露锋芒",
        5,
        3,
        (
            (1, 0, "left"),
            (1, 1, "left"),
            (1, 2, "left"),
            (3, 2, "right"),
            (3, 3, "right"),
            (3, 4, "right"),
            (0, 4, "up"),
            (4, 0, "down"),
        ),
        "从最靠近边界的箭头开始",
    ),
    Level(
        "交错路径",
        6,
        4,
        (
            (0, 1, "up"),
            (1, 1, "up"),
            (5, 4, "down"),
            (4, 4, "down"),
            (2, 0, "left"),
            (2, 2, "left"),
            (2, 3, "up"),
            (1, 5, "right"),
            (3, 5, "right"),
            (3, 3, "right"),
            (3, 2, "down"),
            (4, 0, "left"),
        ),
        "横向与纵向的路线会相互影响",
    ),
    Level(
        "箭阵突围",
        7,
        5,
        (
            (1, 0, "left"), (1, 1, "left"), (1, 2, "left"),
            (1, 4, "right"), (1, 5, "right"), (1, 6, "right"),
            (3, 0, "left"), (3, 1, "left"), (3, 2, "left"),
            (3, 4, "right"), (3, 5, "right"), (3, 6, "right"),
            (5, 0, "left"), (5, 1, "left"), (5, 2, "left"),
            (5, 4, "right"), (5, 5, "right"), (5, 6, "right"),
            (0, 3, "up"), (1, 3, "up"), (2, 3, "up"),
            (4, 3, "down"), (5, 3, "down"), (6, 3, "down"),
        ),
        "观察整条路线，拆解四向箭阵",
    ),
    Level(
        "双轴迷阵",
        8,
        5,
        (
            (1, 0, "left"), (1, 1, "left"), (1, 2, "left"),
            (1, 5, "right"), (1, 6, "right"), (1, 7, "right"),
            (4, 0, "left"), (4, 1, "left"), (4, 2, "left"),
            (4, 5, "right"), (4, 6, "right"), (4, 7, "right"),
            (6, 0, "left"), (6, 1, "left"), (6, 2, "left"),
            (6, 5, "right"), (6, 6, "right"), (6, 7, "right"),
            (0, 3, "up"), (1, 3, "up"), (2, 3, "up"),
            (5, 3, "down"), (6, 3, "down"), (7, 3, "down"),
            (0, 4, "up"), (1, 4, "up"), (2, 4, "up"),
            (5, 4, "down"), (6, 4, "down"), (7, 4, "down"),
        ),
        "两条纵轴把箭阵分成多个清除链",
    ),
    Level(
        "终极箭潮",
        9,
        6,
        (
            (1, 0, "left"), (1, 1, "left"), (1, 2, "left"), (1, 3, "left"),
            (1, 5, "right"), (1, 6, "right"), (1, 7, "right"), (1, 8, "right"),
            (4, 0, "left"), (4, 1, "left"), (4, 2, "left"), (4, 3, "left"),
            (4, 5, "right"), (4, 6, "right"), (4, 7, "right"), (4, 8, "right"),
            (7, 0, "left"), (7, 1, "left"), (7, 2, "left"), (7, 3, "left"),
            (7, 5, "right"), (7, 6, "right"), (7, 7, "right"), (7, 8, "right"),
            (0, 4, "up"), (1, 4, "up"), (2, 4, "up"), (3, 4, "up"),
            (5, 4, "down"), (6, 4, "down"), (7, 4, "down"), (8, 4, "down"),
        ),
        "保持耐心，逐层清理最长的箭头队列",
    ),
)


@dataclass
class FlyAnimation:
    row: int
    col: int
    direction: Direction
    started: float
    duration: float = 0.42


@dataclass
class CollisionAnimation:
    row: int
    col: int
    started: float
    duration: float = 0.58


@dataclass
class FloatText:
    x: float
    y: float
    text: str
    started: float
    color: str
    duration: float = 0.8


class ArrowGame:
    WIDTH = 1000
    HEIGHT = 720

    COLORS = {
        "background": "#F5F3EE",
        "navy": "#183153",
        "navy_soft": "#27496D",
        "blue": "#4285F4",
        "blue_light": "#DCEAFF",
        "coral": "#FF6B5E",
        "coral_light": "#FFE1DD",
        "green": "#26A269",
        "green_light": "#DDF5E9",
        "gold": "#F2B84B",
        "ink": "#243142",
        "muted": "#718096",
        "white": "#FFFFFF",
        "line": "#D9DFE8",
        "cell": "#FFFFFF",
        "cell_alt": "#F9FAFC",
        "shadow": "#D9D7D0",
    }

    SAVE_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "OneArrowAfterAnother"
    SAVE_FILE = SAVE_DIR / "progress.json"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("一箭又一箭 · Python 小游戏")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.minsize(820, 620)
        self.root.configure(bg=self.COLORS["background"])

        self.canvas = tk.Canvas(
            root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=self.COLORS["background"],
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", lambda _event: self.set_hover(None))
        self.root.bind("<Key-r>", lambda _event: self.restart_level())
        self.root.bind("<Key-R>", lambda _event: self.restart_level())
        self.root.bind("<Escape>", lambda _event: self.show_start())
        self.root.bind("<Configure>", self.on_resize)

        self.screen = "start"
        self.level_index = 0
        self.arrows: ArrowMap = {}
        self.mistakes_left = 0
        self.progress = self.load_progress()
        self.level_started = time.monotonic()
        self.finished_elapsed = 0.0
        self.hints_used = 0
        self.undos_used = 0
        self.auto_used = False
        self.auto_solving = False
        self.auto_moves: deque[tuple[int, int]] = deque()
        self.undo_stack: list[tuple[ArrowMap, int]] = []
        self.hint_cell: tuple[int, int] | None = None
        self.hint_until = 0.0
        self.last_timer_second = -1
        self.hover_cell: tuple[int, int] | None = None
        self.hover_button: str | None = None
        self.fly_animations: list[FlyAnimation] = []
        self.collision: CollisionAnimation | None = None
        self.float_texts: list[FloatText] = []
        self.result_kind = ""
        self.input_locked_until = 0.0
        self.board_bounds = (260.0, 146.0, 740.0, 626.0)
        self.buttons: dict[str, tuple[float, float, float, float]] = {}
        self.render()
        self.tick()

    @property
    def level(self) -> Level:
        return LEVELS[self.level_index]

    def load_progress(self) -> dict[str, object]:
        default: dict[str, object] = {
            "unlocked": 1,
            "best_stars": {},
            "best_scores": {},
        }
        try:
            with self.SAVE_FILE.open("r", encoding="utf-8") as file:
                saved = json.load(file)
            if not isinstance(saved, dict):
                return default
            unlocked = max(1, min(len(LEVELS), int(saved.get("unlocked", 1))))
            stars = saved.get("best_stars", {})
            scores = saved.get("best_scores", {})
            return {
                "unlocked": unlocked,
                "best_stars": stars if isinstance(stars, dict) else {},
                "best_scores": scores if isinstance(scores, dict) else {},
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return default

    def save_progress(self) -> None:
        try:
            self.SAVE_DIR.mkdir(parents=True, exist_ok=True)
            with self.SAVE_FILE.open("w", encoding="utf-8") as file:
                json.dump(self.progress, file, ensure_ascii=False, indent=2)
        except OSError:
            # 保存失败不应影响游戏本身。
            pass

    def elapsed_seconds(self) -> int:
        if self.screen == "result":
            return int(self.finished_elapsed)
        return max(0, int(time.monotonic() - self.level_started))

    def current_score(self) -> int:
        mistakes_used = self.level.mistakes - self.mistakes_left
        base = 1000 + self.level_index * 250
        penalties = self.elapsed_seconds() * 5 + mistakes_used * 120 + self.hints_used * 75 + self.undos_used * 30
        if self.auto_used:
            penalties += 500
        return max(0, base - penalties)

    def current_stars(self) -> int:
        if self.auto_used:
            return 1
        mistakes_used = self.level.mistakes - self.mistakes_left
        par_time = 18 + len(self.level.arrows) * 2
        if mistakes_used == 0 and self.hints_used == 0 and self.elapsed_seconds() <= par_time:
            return 3
        if mistakes_used <= 1 and self.hints_used <= 1:
            return 2
        return 1

    def show_start(self) -> None:
        self.cancel_auto()
        self.screen = "start"
        self.fly_animations.clear()
        self.collision = None
        self.float_texts.clear()
        self.render()

    def start_game(self) -> None:
        self.level_index = min(int(self.progress["unlocked"]) - 1, len(LEVELS) - 1)
        self.load_level()

    def show_level_select(self) -> None:
        self.cancel_auto()
        self.screen = "select"
        self.render()

    def select_level(self, index: int) -> None:
        if 0 <= index < int(self.progress["unlocked"]):
            self.level_index = index
            self.load_level()

    def load_level(self) -> None:
        self.cancel_auto()
        self.screen = "game"
        self.arrows = self.level.arrow_map()
        self.mistakes_left = self.level.mistakes
        self.level_started = time.monotonic()
        self.finished_elapsed = 0.0
        self.hints_used = 0
        self.undos_used = 0
        self.auto_used = False
        self.undo_stack.clear()
        self.hint_cell = None
        self.hint_until = 0.0
        self.last_timer_second = -1
        self.fly_animations.clear()
        self.collision = None
        self.float_texts.clear()
        self.result_kind = ""
        self.input_locked_until = 0.0
        self.render()

    def restart_level(self) -> None:
        if self.screen in {"game", "result"}:
            self.load_level()

    def next_level(self) -> None:
        if self.level_index + 1 < len(LEVELS):
            self.level_index += 1
            self.load_level()
        else:
            self.show_start()

    def cancel_auto(self) -> None:
        self.auto_solving = False
        self.auto_moves.clear()

    def set_hover(self, value: tuple[int, int] | None) -> None:
        if value != self.hover_cell:
            self.hover_cell = value
            self.render()

    def on_resize(self, event: tk.Event) -> None:
        if event.widget is self.root:
            self.WIDTH = max(820, event.width)
            self.HEIGHT = max(620, event.height)
            self.render()

    def rounded_rect(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float,
        **kwargs: object,
    ) -> int:
        radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def draw_button(
        self,
        name: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        text: str,
        *,
        primary: bool = True,
    ) -> None:
        self.buttons[name] = (x1, y1, x2, y2)
        hovered = self.hover_button == name
        if primary:
            fill = self.COLORS["navy_soft"] if hovered else self.COLORS["navy"]
            foreground = self.COLORS["white"]
            outline = fill
        else:
            fill = self.COLORS["blue_light"] if hovered else self.COLORS["white"]
            foreground = self.COLORS["navy"]
            outline = self.COLORS["line"]
        if primary:
            self.rounded_rect(x1 + 2, y1 + 5, x2 + 2, y2 + 5, 13, fill="#CAC8C2", outline="")
        self.rounded_rect(x1, y1, x2, y2, 13, fill=fill, outline=outline, width=1)
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            fill=foreground,
            font=("Microsoft YaHei UI", 12, "bold"),
        )

    def render(self) -> None:
        self.canvas.delete("all")
        self.buttons.clear()
        self.canvas.configure(bg=self.COLORS["background"])
        if self.screen == "start":
            self.render_start()
        elif self.screen == "select":
            self.render_level_select()
        elif self.screen == "game":
            self.render_game()
        else:
            self.render_game(draw_overlay=False)
            self.render_result()

    def render_start(self) -> None:
        width, height = self.WIDTH, self.HEIGHT
        cx = width / 2

        # 装饰性箭头轨迹
        decorations = [
            (70, 115, "right", self.COLORS["blue"]),
            (width - 80, 165, "down", self.COLORS["gold"]),
            (100, height - 110, "up", self.COLORS["coral"]),
            (width - 100, height - 100, "left", self.COLORS["green"]),
        ]
        for x, y, direction, color in decorations:
            self.draw_arrow(x, y, 26, direction, color, alpha_style="soft")

        self.canvas.create_text(
            cx,
            105,
            text="一箭又一箭",
            fill=self.COLORS["navy"],
            font=("Microsoft YaHei UI", 38, "bold"),
        )
        self.canvas.create_text(
            cx,
            157,
            text="ONE ARROW AFTER ANOTHER",
            fill=self.COLORS["muted"],
            font=("Segoe UI", 11, "bold"),
        )

        card_w, card_h = min(600, width - 180), 270
        x1, y1 = cx - card_w / 2, 205
        x2, y2 = cx + card_w / 2, y1 + card_h
        self.rounded_rect(x1 + 5, y1 + 8, x2 + 5, y2 + 8, 24, fill=self.COLORS["shadow"], outline="")
        self.rounded_rect(x1, y1, x2, y2, 24, fill=self.COLORS["white"], outline="")

        self.canvas.create_text(
            cx,
            y1 + 42,
            text="让每支箭找到离场的路",
            fill=self.COLORS["ink"],
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        rules = [
            ("01", "点击箭头", "选择想要发射的箭头"),
            ("02", "检查路径", "前方无箭头时才能飞出"),
            ("03", "谨慎尝试", "碰撞会消耗一次失误机会"),
        ]
        for index, (number, title, detail) in enumerate(rules):
            row_y = y1 + 92 + index * 54
            self.rounded_rect(x1 + 35, row_y - 18, x1 + 71, row_y + 18, 10, fill=self.COLORS["blue_light"], outline="")
            self.canvas.create_text(x1 + 53, row_y, text=number, fill=self.COLORS["blue"], font=("Segoe UI", 10, "bold"))
            self.canvas.create_text(x1 + 92, row_y - 8, text=title, anchor="w", fill=self.COLORS["ink"], font=("Microsoft YaHei UI", 12, "bold"))
            self.canvas.create_text(x1 + 92, row_y + 12, text=detail, anchor="w", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 9))

        continue_level = min(int(self.progress["unlocked"]), len(LEVELS))
        self.draw_button("start", cx - 220, y2 + 35, cx - 10, y2 + 93, f"继续挑战 · 第 {continue_level} 关")
        self.draw_button("level_select", cx + 10, y2 + 35, cx + 220, y2 + 93, "关卡选择", primary=False)
        self.canvas.create_text(
            cx,
            height - 38,
            text="鼠标点击操作  ·  R 重新开始  ·  Esc 返回首页",
            fill=self.COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        )

    def render_level_select(self) -> None:
        width, height = self.WIDTH, self.HEIGHT
        self.canvas.create_text(width / 2, 62, text="选择关卡", fill=self.COLORS["navy"], font=("Microsoft YaHei UI", 28, "bold"))
        self.canvas.create_text(width / 2, 102, text="通关后会自动解锁下一关，成绩保存在本机", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 10))
        self.draw_button("back", 40, 35, 125, 75, "← 返回", primary=False)

        card_w = min(250, (width - 140) / 3)
        card_h = 190
        gap_x = 25
        total_top_w = card_w * 3 + gap_x * 2
        start_x = (width - total_top_w) / 2
        positions = []
        for index in range(len(LEVELS)):
            if index < 3:
                positions.append((start_x + index * (card_w + gap_x), 145))
            else:
                bottom_total = card_w * 2 + gap_x
                positions.append(((width - bottom_total) / 2 + (index - 3) * (card_w + gap_x), 365))

        unlocked = int(self.progress["unlocked"])
        best_stars = self.progress["best_stars"]
        best_scores = self.progress["best_scores"]
        for index, (x1, y1) in enumerate(positions):
            x2, y2 = x1 + card_w, y1 + card_h
            available = index < unlocked
            fill = self.COLORS["white"] if available else "#E9E9E6"
            self.rounded_rect(x1 + 4, y1 + 6, x2 + 4, y2 + 6, 19, fill=self.COLORS["shadow"], outline="")
            self.rounded_rect(x1, y1, x2, y2, 19, fill=fill, outline="")
            badge = self.COLORS["blue"] if available else self.COLORS["muted"]
            self.canvas.create_oval(x1 + 22, y1 + 20, x1 + 66, y1 + 64, fill=self.COLORS["blue_light"] if available else "#DDDDDA", outline="")
            self.canvas.create_text(x1 + 44, y1 + 42, text=str(index + 1), fill=badge, font=("Segoe UI", 15, "bold"))
            self.canvas.create_text(x1 + 22, y1 + 88, text=LEVELS[index].name if available else "尚未解锁", anchor="w", fill=self.COLORS["ink"] if available else self.COLORS["muted"], font=("Microsoft YaHei UI", 14, "bold"))
            arrows_text = f"{LEVELS[index].size}×{LEVELS[index].size}  ·  {len(LEVELS[index].arrows)} 支箭"
            self.canvas.create_text(x1 + 22, y1 + 119, text=arrows_text, anchor="w", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 9))
            if available:
                stars = int(best_stars.get(str(index), 0)) if isinstance(best_stars, dict) else 0
                score = int(best_scores.get(str(index), 0)) if isinstance(best_scores, dict) else 0
                star_text = "★" * stars + "☆" * (3 - stars)
                self.canvas.create_text(x1 + 22, y1 + 151, text=star_text, anchor="w", fill=self.COLORS["gold"], font=("Microsoft YaHei UI", 13, "bold"))
                self.canvas.create_text(x2 - 22, y1 + 153, text=f"最高 {score}", anchor="e", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 8))
                self.buttons[f"select_{index}"] = (x1, y1, x2, y2)
            else:
                self.canvas.create_text(x1 + 22, y1 + 153, text="🔒 通关前一关后解锁", anchor="w", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 9))

        self.canvas.create_text(width / 2, height - 33, text="提示：获得星级不影响关卡解锁", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 9))

    def layout_board(self) -> tuple[float, float, float]:
        available_h = self.HEIGHT - 250
        size = min(460.0, available_h, self.WIDTH - 390)
        size = max(360.0, size)
        left = (self.WIDTH - size) / 2
        top = 138.0
        self.board_bounds = (left, top, left + size, top + size)
        return left, top, size / self.level.size

    def render_game(self, draw_overlay: bool = True) -> None:
        width = self.WIDTH
        self.canvas.create_text(40, 34, text="一箭又一箭", anchor="w", fill=self.COLORS["navy"], font=("Microsoft YaHei UI", 18, "bold"))
        self.canvas.create_text(40, 61, text="ONE ARROW AFTER ANOTHER", anchor="w", fill=self.COLORS["muted"], font=("Segoe UI", 8, "bold"))
        self.draw_button("home", width - 125, 25, width - 40, 65, "首页", primary=False)

        hud_y = 87
        self.draw_stat_card(40, hud_y, 190, "关卡", f"{self.level_index + 1} / {len(LEVELS)}", self.COLORS["blue"])
        self.draw_stat_card(205, hud_y, 355, "剩余箭头", str(len(self.arrows)), self.COLORS["green"])
        self.draw_stat_card(width - 355, hud_y, width - 205, "失误机会", "●" * self.mistakes_left + "○" * (self.level.mistakes - self.mistakes_left), self.COLORS["coral"])
        self.draw_button("restart", width - 190, hud_y, width - 40, hud_y + 54, "↻  重新开始", primary=False)

        left, top, cell = self.layout_board()
        board_size = cell * self.level.size
        self.rounded_rect(left + 7, top + 9, left + board_size + 7, top + board_size + 9, 20, fill=self.COLORS["shadow"], outline="")
        self.rounded_rect(left - 5, top - 5, left + board_size + 5, top + board_size + 5, 20, fill=self.COLORS["white"], outline="")

        for row in range(self.level.size):
            for col in range(self.level.size):
                x1 = left + col * cell + 3
                y1 = top + row * cell + 3
                x2 = x1 + cell - 6
                y2 = y1 + cell - 6
                fill = self.COLORS["cell_alt"] if (row + col) % 2 else self.COLORS["cell"]
                if self.hint_cell == (row, col) and time.monotonic() < self.hint_until:
                    fill = self.COLORS["green_light"]
                if self.hover_cell == (row, col) and (row, col) in self.arrows:
                    fill = self.COLORS["blue_light"]
                self.rounded_rect(x1, y1, x2, y2, max(5, cell * 0.10), fill=fill, outline=self.COLORS["line"], width=1)

        now = time.monotonic()
        for (row, col), direction in self.arrows.items():
            x = left + (col + 0.5) * cell
            y = top + (row + 0.5) * cell
            color = self.COLORS["navy"]
            if self.hint_cell == (row, col) and now < self.hint_until:
                color = self.COLORS["green"]
            offset_x = 0.0
            offset_y = 0.0
            scale = 1.0
            if self.collision and (row, col) == (self.collision.row, self.collision.col):
                elapsed = now - self.collision.started
                progress = elapsed / self.collision.duration
                if progress < 1:
                    dr, dc = DIRECTION_VECTORS[direction]
                    bump = math.sin(progress * math.pi * 4) * (1 - progress) * cell * 0.12
                    offset_x = dc * bump
                    offset_y = dr * bump
                    color = self.COLORS["coral"] if int(progress * 8) % 2 == 0 else self.COLORS["navy"]
                    scale = 1.08
            self.draw_arrow(x + offset_x, y + offset_y, cell * 0.29 * scale, direction, color)

        for animation in self.fly_animations:
            elapsed = now - animation.started
            progress = min(1.0, elapsed / animation.duration)
            eased = 1 - (1 - progress) ** 3
            dr, dc = DIRECTION_VECTORS[animation.direction]
            x = left + (animation.col + 0.5) * cell + dc * board_size * 1.05 * eased
            y = top + (animation.row + 0.5) * cell + dr * board_size * 1.05 * eased
            self.draw_arrow(x, y, cell * 0.29, animation.direction, self.COLORS["blue"])

        for floating in self.float_texts:
            progress = min(1.0, (now - floating.started) / floating.duration)
            self.canvas.create_text(
                floating.x,
                floating.y - 30 * progress,
                text=floating.text,
                fill=floating.color,
                font=("Microsoft YaHei UI", 12, "bold"),
            )

        footer_y = min(self.HEIGHT - 32, top + board_size + 34)
        self.canvas.create_text(width / 2, footer_y, text=f"第 {self.level_index + 1} 关 · {self.level.name}  —  {self.level.subtitle}", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 10))

        # 棋盘两侧的信息和辅助工具。
        left_panel_x2 = left - 24
        if left_panel_x2 - 40 >= 115:
            self.draw_stat_card(40, top + 35, left_panel_x2, "用时", f"{self.elapsed_seconds()} 秒", self.COLORS["blue"])
            self.draw_stat_card(40, top + 103, left_panel_x2, "当前得分", str(self.current_score()), self.COLORS["gold"])
            self.canvas.create_text((40 + left_panel_x2) / 2, top + 188, text="实时评价", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 8))
            self.canvas.create_text((40 + left_panel_x2) / 2, top + 218, text="★" * self.current_stars() + "☆" * (3 - self.current_stars()), fill=self.COLORS["gold"], font=("Microsoft YaHei UI", 16, "bold"))

        tools_x1, tools_x2 = left + board_size + 24, width - 40
        if tools_x2 - tools_x1 >= 115:
            self.canvas.create_text(tools_x1, top + 28, text="辅助工具", anchor="w", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 9, "bold"))
            self.draw_button("hint", tools_x1, top + 48, tools_x2, top + 96, "提示一步", primary=False)
            self.draw_button("undo", tools_x1, top + 108, tools_x2, top + 156, "撤销上步", primary=False)
            self.draw_button("auto", tools_x1, top + 168, tools_x2, top + 216, "停止演示" if self.auto_solving else "AI 自动解题", primary=False)
            self.canvas.create_text(tools_x1, top + 244, text="提示与撤销会扣分\n自动解题最高 1 星", anchor="nw", justify="left", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 8))

    def draw_stat_card(self, x1: float, y1: float, x2: float, label: str, value: str, accent: str) -> None:
        self.rounded_rect(x1, y1, x2, y1 + 54, 14, fill=self.COLORS["white"], outline=self.COLORS["line"], width=1)
        self.canvas.create_rectangle(x1, y1 + 10, x1 + 4, y1 + 44, fill=accent, outline="")
        self.canvas.create_text(x1 + 18, y1 + 16, text=label, anchor="w", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 8))
        size = 11 if "●" in value else 14
        self.canvas.create_text(x1 + 18, y1 + 37, text=value, anchor="w", fill=accent, font=("Microsoft YaHei UI", size, "bold"))

    def draw_arrow(
        self,
        x: float,
        y: float,
        radius: float,
        direction: Direction,
        color: str,
        alpha_style: str = "normal",
    ) -> None:
        # 箭头基础形状朝右，再旋转到目标方向。
        points = [
            (-0.82, -0.20), (0.12, -0.20), (0.12, -0.55),
            (0.86, 0.00), (0.12, 0.55), (0.12, 0.20), (-0.82, 0.20),
        ]
        angles = {"right": 0, "down": math.pi / 2, "left": math.pi, "up": -math.pi / 2}
        angle = angles[direction]
        rotated: list[float] = []
        for px, py in points:
            rx = px * math.cos(angle) - py * math.sin(angle)
            ry = px * math.sin(angle) + py * math.cos(angle)
            rotated.extend([x + rx * radius, y + ry * radius])
        if alpha_style == "soft":
            self.canvas.create_oval(x - radius * 1.25, y - radius * 1.25, x + radius * 1.25, y + radius * 1.25, fill=self.COLORS["white"], outline="")
        self.canvas.create_polygon(rotated, fill=color, outline="", smooth=False)

    def render_result(self) -> None:
        width, height = self.WIDTH, self.HEIGHT
        self.canvas.create_rectangle(0, 0, width, height, fill="#A7AFB8", outline="", stipple="gray50")
        card_w, card_h = 480, 350
        x1, y1 = width / 2 - card_w / 2, height / 2 - card_h / 2
        x2, y2 = x1 + card_w, y1 + card_h
        self.rounded_rect(x1 + 6, y1 + 9, x2 + 6, y2 + 9, 25, fill="#5B6570", outline="")
        self.rounded_rect(x1, y1, x2, y2, 25, fill=self.COLORS["white"], outline="")

        won = self.result_kind in {"win", "complete"}
        accent = self.COLORS["green"] if won else self.COLORS["coral"]
        pale = self.COLORS["green_light"] if won else self.COLORS["coral_light"]
        icon = "✓" if won else "!"
        title = "全部通关！" if self.result_kind == "complete" else ("本关通过！" if won else "挑战失败")
        detail = (
            "五座箭阵已全部清除，漂亮的判断！"
            if self.result_kind == "complete"
            else ("箭头全部离场，准备迎接下一关。" if won else "失误机会已经用完，再观察一下路径吧。")
        )
        self.canvas.create_oval(width / 2 - 42, y1 + 36, width / 2 + 42, y1 + 120, fill=pale, outline="")
        self.canvas.create_text(width / 2, y1 + 78, text=icon, fill=accent, font=("Segoe UI", 31, "bold"))
        self.canvas.create_text(width / 2, y1 + 159, text=title, fill=self.COLORS["ink"], font=("Microsoft YaHei UI", 24, "bold"))
        self.canvas.create_text(width / 2, y1 + 202, text=detail, fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 10))

        if won:
            self.canvas.create_text(width / 2 - 80, y1 + 226, text="★" * self.current_stars() + "☆" * (3 - self.current_stars()), fill=self.COLORS["gold"], font=("Microsoft YaHei UI", 15, "bold"))
            self.canvas.create_text(width / 2 + 55, y1 + 226, text=f"{self.current_score()} 分  ·  {self.elapsed_seconds()} 秒", anchor="w", fill=self.COLORS["ink"], font=("Microsoft YaHei UI", 9, "bold"))

        if self.result_kind == "win":
            self.draw_button("next", width / 2 - 105, y1 + 252, width / 2 + 105, y1 + 308, "下一关  →")
        elif self.result_kind == "complete":
            self.draw_button("again", width / 2 - 105, y1 + 252, width / 2 + 105, y1 + 308, "再玩一次")
        else:
            self.draw_button("retry", width / 2 - 105, y1 + 252, width / 2 + 105, y1 + 308, "↻  重试本关")
        self.canvas.create_text(width / 2, y1 + 329, text="R 键也可以快速重新开始", fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 8))

    def board_cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        left, top, right, bottom = self.board_bounds
        if not (left <= x < right and top <= y < bottom):
            return None
        cell = (right - left) / self.level.size
        row = int((y - top) / cell)
        col = int((x - left) / cell)
        return row, col

    def button_at(self, x: float, y: float) -> str | None:
        for name, (x1, y1, x2, y2) in self.buttons.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return None

    def on_motion(self, event: tk.Event) -> None:
        button = self.button_at(event.x, event.y)
        cell = self.board_cell_at(event.x, event.y) if self.screen == "game" else None
        if cell not in self.arrows:
            cell = None
        if button != self.hover_button or cell != self.hover_cell:
            self.hover_button = button
            self.hover_cell = cell
            self.canvas.configure(cursor="hand2" if button or cell else "")
            self.render()

    def on_click(self, event: tk.Event) -> None:
        button = self.button_at(event.x, event.y)
        if button == "start" or button == "again":
            self.start_game()
            return
        if button == "level_select":
            self.show_level_select()
            return
        if button == "back":
            self.show_start()
            return
        if button and button.startswith("select_"):
            self.select_level(int(button.split("_")[1]))
            return
        if button == "home":
            self.show_start()
            return
        if button in {"restart", "retry"}:
            self.restart_level()
            return
        if button == "next":
            self.next_level()
            return
        if button == "hint":
            self.show_hint()
            return
        if button == "undo":
            self.undo_move()
            return
        if button == "auto":
            self.toggle_auto_solve()
            return

        if self.screen != "game" or self.auto_solving or time.monotonic() < self.input_locked_until:
            return
        cell = self.board_cell_at(event.x, event.y)
        if cell is None or cell not in self.arrows:
            return
        self.try_arrow(*cell)

    def try_arrow(self, row: int, col: int, *, record_undo: bool = True) -> None:
        direction = self.arrows[(row, col)]
        now = time.monotonic()
        left, top, right, _bottom = self.board_bounds
        cell = (right - left) / self.level.size
        x = left + (col + 0.5) * cell
        y = top + (row + 0.5) * cell

        if record_undo:
            self.undo_stack.append((dict(self.arrows), self.mistakes_left))
        self.hint_cell = None

        if path_is_clear(self.arrows, row, col, direction, self.level.size):
            del self.arrows[(row, col)]
            self.fly_animations.append(FlyAnimation(row, col, direction, now))
            self.float_texts.append(FloatText(x, y, "路径畅通", now, self.COLORS["green"], 0.65))
            if not self.arrows:
                self.input_locked_until = now + 0.65
                self.root.after(650, self.finish_level)
            elif self.auto_solving:
                self.root.after(470, self.perform_auto_step)
        else:
            self.mistakes_left -= 1
            self.collision = CollisionAnimation(row, col, now)
            self.float_texts.append(FloatText(x, y, "前方有阻挡  -1", now, self.COLORS["coral"]))
            self.input_locked_until = now + 0.28
            if self.mistakes_left <= 0:
                self.input_locked_until = now + 0.75
                self.root.after(750, self.fail_level)
        self.render()

    def show_hint(self) -> None:
        if self.screen != "game" or self.auto_solving or not self.arrows:
            return
        solution = find_solution(self.arrows, self.level.size)
        if not solution:
            return
        self.hint_cell = solution[0]
        self.hint_until = time.monotonic() + 2.0
        self.hints_used += 1
        self.render()

    def undo_move(self) -> None:
        if self.screen != "game" or self.auto_solving or not self.undo_stack:
            return
        self.arrows, self.mistakes_left = self.undo_stack.pop()
        self.undos_used += 1
        self.fly_animations.clear()
        self.float_texts.clear()
        self.collision = None
        self.hint_cell = None
        self.input_locked_until = 0.0
        self.render()

    def toggle_auto_solve(self) -> None:
        if self.screen != "game":
            return
        if self.auto_solving:
            self.cancel_auto()
            self.render()
            return
        solution = find_solution(self.arrows, self.level.size)
        if not solution:
            return
        self.auto_moves = deque(solution)
        self.auto_solving = True
        self.auto_used = True
        self.hint_cell = None
        self.perform_auto_step()

    def perform_auto_step(self) -> None:
        if self.screen != "game" or not self.auto_solving:
            return
        while self.auto_moves:
            row, col = self.auto_moves.popleft()
            if (row, col) in self.arrows:
                self.try_arrow(row, col, record_undo=False)
                return
        self.auto_solving = False
        self.render()

    def finish_level(self) -> None:
        if self.screen != "game" or self.arrows:
            return
        self.cancel_auto()
        self.finished_elapsed = time.monotonic() - self.level_started
        stars = self.current_stars()
        score = self.current_score()
        best_stars = self.progress["best_stars"]
        best_scores = self.progress["best_scores"]
        if isinstance(best_stars, dict):
            best_stars[str(self.level_index)] = max(int(best_stars.get(str(self.level_index), 0)), stars)
        if isinstance(best_scores, dict):
            best_scores[str(self.level_index)] = max(int(best_scores.get(str(self.level_index), 0)), score)
        self.progress["unlocked"] = min(len(LEVELS), max(int(self.progress["unlocked"]), self.level_index + 2))
        self.save_progress()
        self.result_kind = "complete" if self.level_index == len(LEVELS) - 1 else "win"
        self.screen = "result"
        self.render()

    def fail_level(self) -> None:
        if self.screen != "game" or self.mistakes_left > 0:
            return
        self.result_kind = "fail"
        self.cancel_auto()
        self.finished_elapsed = time.monotonic() - self.level_started
        self.screen = "result"
        self.render()

    def tick(self) -> None:
        now = time.monotonic()
        old_flying = len(self.fly_animations)
        old_floating = len(self.float_texts)
        had_collision = self.collision is not None
        self.fly_animations = [item for item in self.fly_animations if now - item.started < item.duration]
        self.float_texts = [item for item in self.float_texts if now - item.started < item.duration]
        if self.collision and now - self.collision.started >= self.collision.duration:
            self.collision = None
        if self.hint_cell and now >= self.hint_until:
            self.hint_cell = None

        animating = bool(self.fly_animations or self.float_texts or self.collision)
        changed = old_flying != len(self.fly_animations) or old_floating != len(self.float_texts) or had_collision != (self.collision is not None)
        timer_second = self.elapsed_seconds() if self.screen == "game" else -1
        timer_changed = timer_second != self.last_timer_second
        self.last_timer_second = timer_second
        if self.screen == "game" and (animating or changed or timer_changed or self.hint_cell is not None):
            self.render()
        self.root.after(16, self.tick)


def validate_levels(levels: Iterable[Level] = LEVELS) -> None:
    """启动前验证关卡数据，便于开发者发现坐标、方向或无解问题。"""
    for index, level in enumerate(levels, start=1):
        if level.size < 2:
            raise ValueError(f"第 {index} 关棋盘尺寸无效")
        positions: set[tuple[int, int]] = set()
        directions: set[str] = set()
        for row, col, direction in level.arrows:
            if not (0 <= row < level.size and 0 <= col < level.size):
                raise ValueError(f"第 {index} 关箭头 {(row, col)} 越界")
            if direction not in DIRECTION_VECTORS:
                raise ValueError(f"第 {index} 关方向 {direction!r} 无效")
            if (row, col) in positions:
                raise ValueError(f"第 {index} 关坐标 {(row, col)} 重复")
            positions.add((row, col))
            directions.add(direction)
        if directions != set(DIRECTION_VECTORS):
            raise ValueError(f"第 {index} 关没有包含四种方向")
        if find_solution(level.arrow_map(), level.size) is None:
            raise ValueError(f"第 {index} 关无解")


def main() -> None:
    validate_levels()
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.25)
    except tk.TclError:
        pass
    ArrowGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
