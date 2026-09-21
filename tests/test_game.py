import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import one_arrow_after_another as game


class PathRuleTests(unittest.TestCase):
    def test_clear_paths_in_all_four_directions(self):
        cases = [
            ({(2, 2): "up", (3, 0): "right"}, (2, 2), "up"),
            ({(2, 2): "down", (1, 4): "left"}, (2, 2), "down"),
            ({(2, 2): "left", (4, 3): "up"}, (2, 2), "left"),
            ({(2, 2): "right", (0, 1): "down"}, (2, 2), "right"),
        ]
        for arrows, position, direction in cases:
            with self.subTest(direction=direction):
                self.assertTrue(game.path_is_clear(arrows, *position, direction, 5))

    def test_blocked_paths_in_all_four_directions(self):
        cases = [
            ({(2, 2): "up", (0, 2): "right"}, (2, 2), "up"),
            ({(2, 2): "down", (4, 2): "left"}, (2, 2), "down"),
            ({(2, 2): "left", (2, 0): "up"}, (2, 2), "left"),
            ({(2, 2): "right", (2, 4): "down"}, (2, 2), "right"),
        ]
        for arrows, position, direction in cases:
            with self.subTest(direction=direction):
                self.assertFalse(game.path_is_clear(arrows, *position, direction, 5))

    def test_only_forward_cells_matter(self):
        arrows = {(2, 2): "right", (2, 0): "left", (0, 2): "down"}
        self.assertTrue(game.path_is_clear(arrows, 2, 2, "right", 5))


class LevelTests(unittest.TestCase):
    def test_all_levels_have_complete_solution(self):
        game.validate_levels()
        for level in game.LEVELS:
            solution = game.find_solution(level.arrow_map(), level.size)
            self.assertIsNotNone(solution)
            self.assertEqual(len(solution), len(level.arrows))

    def test_solution_moves_are_legal(self):
        for level in game.LEVELS:
            arrows = level.arrow_map()
            for row, col in game.find_solution(arrows, level.size) or []:
                direction = arrows[(row, col)]
                self.assertTrue(game.path_is_clear(arrows, row, col, direction, level.size))
                del arrows[(row, col)]
            self.assertFalse(arrows)


class InterfaceSmokeTest(unittest.TestCase):
    def test_all_screens_render(self):
        root = tk.Tk()
        root.withdraw()
        app = game.ArrowGame(root)
        root.update_idletasks()
        self.assertGreater(len(app.canvas.find_all()), 10)
        app.start_game()
        root.update_idletasks()
        self.assertEqual(app.screen, "game")
        app.show_level_select()
        root.update_idletasks()
        self.assertEqual(app.screen, "select")
        self.assertIn("select_0", app.buttons)
        app.select_level(0)
        app.result_kind = "win"
        app.screen = "result"
        app.render()
        root.update_idletasks()
        self.assertIn("next", app.buttons)
        root.destroy()

    def test_hint_undo_and_auto_solver(self):
        root = tk.Tk()
        root.withdraw()
        app = game.ArrowGame(root)
        app.level_index = 0
        app.load_level()

        initial_arrows = dict(app.arrows)
        initial_mistakes = app.mistakes_left
        app.try_arrow(1, 1)  # 左侧 (1, 0) 仍在，必然碰撞。
        self.assertEqual(app.mistakes_left, initial_mistakes - 1)
        app.undo_move()
        self.assertEqual(app.arrows, initial_arrows)
        self.assertEqual(app.mistakes_left, initial_mistakes)

        app.show_hint()
        self.assertIsNotNone(app.hint_cell)
        row, col = app.hint_cell
        self.assertTrue(game.path_is_clear(app.arrows, row, col, app.arrows[(row, col)], app.level.size))

        before_auto = len(app.arrows)
        app.toggle_auto_solve()
        self.assertTrue(app.auto_used)
        self.assertEqual(len(app.arrows), before_auto - 1)
        app.cancel_auto()
        root.destroy()

    def test_progress_save_and_reload(self):
        root = tk.Tk()
        root.withdraw()
        app = game.ArrowGame(root)
        with tempfile.TemporaryDirectory(dir="work") as temp_dir:
            app.SAVE_DIR = Path(temp_dir)
            app.SAVE_FILE = Path(temp_dir) / "progress.json"
            app.progress = {"unlocked": 3, "best_stars": {"0": 3}, "best_scores": {"0": 900}}
            app.save_progress()
            loaded = app.load_progress()
            self.assertEqual(loaded["unlocked"], 3)
            self.assertEqual(loaded["best_stars"], {"0": 3})
            self.assertEqual(loaded["best_scores"], {"0": 900})
        root.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
