"""Regression checks for the forecast's loading lifecycle."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "solarcast_loading", Path(__file__).resolve().parents[1] / "app" / "loading.py"
)
loading = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loading)


class LoadingTests(unittest.TestCase):
    def test_each_navigation_has_a_distinct_scene_and_replays(self):
        scenes = set()
        with patch.object(loading, "st", Mock()) as ui, patch.object(loading, "sleep"):
            for page in loading.PAGE_LOADERS:
                for _ in range(2):
                    slot = Mock()
                    ui.empty.return_value = slot
                    with loading.PageLoading(page):
                        pass
                    markup = slot.markdown.call_args.args[0]
                    self.assertIn(page, markup)
                    self.assertEqual(markup.count('style="--segment:'), 10)
                    slot.empty.assert_called_once()
                    scenes.add(markup)
        self.assertEqual(len(scenes), 10)

    def test_navigation_failure_clears_without_delay(self):
        with patch.object(loading, "st", Mock()) as ui, patch.object(loading, "sleep") as delay:
            with self.assertRaises(RuntimeError):
                with loading.PageLoading("Power history"):
                    raise RuntimeError("Failed to load")
            ui.empty.return_value.empty.assert_called_once()
            delay.assert_not_called()

    def test_normal_page_interaction_skips_navigation_loader(self):
        with patch.object(loading, "st", Mock()) as ui, patch.object(loading, "sleep") as delay:
            with loading.PageLoading("Manual prediction", enabled=False):
                pass
            ui.empty.assert_not_called()
            delay.assert_not_called()

    def test_refresh_skips_animation_and_delays(self):
        ui = Mock()
        with patch.object(loading, "st", ui), patch.object(loading, "sleep") as sleep:
            with loading.SolarLoading(enabled=False) as indicator:
                indicator.update(1)
                indicator.update(2)
                indicator.update(3)
        ui.empty.assert_not_called()
        sleep.assert_not_called()

    def test_completion_and_repeated_attempts(self):
        ui = Mock()
        attempts = [(Mock(), Mock()), (Mock(), Mock())]
        ui.empty.side_effect = [slot for attempt in attempts for slot in attempt]
        with patch.object(loading, "st", ui), patch.object(loading, "sleep"):
            for scene, status in attempts:
                with loading.SolarLoading() as indicator:
                    indicator.update(1)
                    indicator.update(2)
                    indicator.update(3)
                # Progress must never remount or restart the day/night scene.
                scene.markdown.assert_called_once()
                scene_html = scene.markdown.call_args.args[0]
                self.assertIn("sc-village-night", scene_html)
                self.assertIn("sc-village-day", scene_html)
                html = [call.args[0] for call in status.markdown.call_args_list]
                self.assertEqual(len(html), 4)
                for page, progress in zip(html, (0, 33, 67, 100)):
                    self.assertIn(f'>{progress}<span>%</span>', page)
                self.assertIn("Your outlook is ready", html[-1])
                scene.empty.assert_called_once()
                status.empty.assert_called_once()

    def test_failure_clears_screen_without_showing_completion(self):
        ui = Mock()
        scene, status = Mock(), Mock()
        ui.empty.side_effect = (scene, status)
        with patch.object(loading, "st", ui), patch.object(loading, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "weather failed"):
                with loading.SolarLoading():
                    raise RuntimeError("weather failed")
        scene.empty.assert_called_once()
        status.empty.assert_called_once()
        self.assertNotIn("Your outlook is ready", status.markdown.call_args.args[0])

    def test_unknown_stage_is_rejected_cleanly(self):
        with patch.object(loading, "st", Mock()):
            indicator = loading.SolarLoading()
            for stage in (-1, 4, None, "3"):
                with self.subTest(stage=stage):
                    with self.assertRaisesRegex(ValueError, "Unknown loading stage"):
                        indicator.update(stage)

    def test_fast_load_plays_full_cycle_before_clearing(self):
        now = [0.0]

        def advance(seconds):
            now[0] += seconds

        with patch.object(loading, "st", Mock()), patch.object(loading, "monotonic", side_effect=lambda: now[0]), patch.object(loading, "sleep", side_effect=advance):
            with loading.SolarLoading() as indicator:
                indicator.update(1)
                indicator.update(2)
                indicator.update(3)
                self.assertAlmostEqual(now[0], loading.SCENE_DURATION - .6)
            self.assertAlmostEqual(now[0], loading.SCENE_DURATION)

    def test_animation_uses_same_duration_as_display_timer(self):
        ui = Mock()
        scene, status = Mock(), Mock()
        ui.empty.side_effect = (scene, status)
        with patch.object(loading, "st", ui), patch.object(loading, "sleep"):
            with loading.SolarLoading(minimum_duration=12.0):
                pass
        self.assertIn('--sc-cycle:12.0s', scene.markdown.call_args.args[0])

    def test_reduced_motion_preserves_day_night_fades(self):
        css_source = (Path(__file__).resolve().parents[1] / "app" / "styles.py").read_text(encoding="utf-8")
        dashboard_css = css_source.split("def apply_styles():", 1)[1]
        reduced = dashboard_css.split('@media (prefers-reduced-motion:reduce) {', 1)[1].split('[data-testid="stButton"]', 1)[0]
        disabled_selectors = reduced.split('{animation:none;}', 1)[0]
        self.assertNotIn('.sc-village-day', disabled_selectors)
        self.assertNotIn('.sc-daybreak', disabled_selectors)
        self.assertIn('animation:sc-solar-visibility', reduced)


if __name__ == "__main__":
    unittest.main()
