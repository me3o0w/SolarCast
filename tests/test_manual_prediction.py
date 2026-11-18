"""Simplified manual inputs preserve model units and valid calendar features."""

from datetime import date, time
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import manual_pred


class ManualPredictionTests(unittest.TestCase):
    def setUp(self):
        self.power = Mock(predict=Mock(return_value=[500.0]))
        self.temperature = Mock(predict=Mock(return_value=[42.0]))
        for name, value in (("model", self.power), ("module_temp_model", self.temperature)):
            replacement = patch.object(manual_pred, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def app(self):
        app = AppTest.from_string("from manual_pred import render_manual_prediction\nrender_manual_prediction()").run()
        self.assertEqual(len(app.exception), 0)
        self.power.predict.assert_not_called()
        return app

    def test_date_time_and_sunlight_are_converted_for_models(self):
        app = self.app()
        app.date_input(key="manual_date").set_value(date(2028, 2, 29))
        app.time_input(key="manual_time").set_value(time(14, 30))
        app.number_input(key="manual_sunlight").set_value(650.0)
        app.button(key="manual_prediction_button").click().run()
        self.assertEqual(len(app.exception), 0)
        features = self.power.predict.call_args.args[0].iloc[0]
        self.assertAlmostEqual(features.IRRADIATION, .65)
        self.assertEqual(features.MODULE_TEMPERATURE, 42)
        self.assertEqual((features.HOUR, features.MINUTE, features.DAY, features.MONTH, features.DAY_OF_WEEK),
                         (14, 30, 29, 2, 1))
        self.temperature.predict.assert_called_once()
        self.assertEqual(app.metric[0].value, "500.00")

    def test_optional_measured_panel_temperature_skips_estimation(self):
        app = self.app()
        app.number_input(key="manual_module_temperature").set_value(38.5)
        app.button(key="manual_prediction_button").click().run()
        self.assertEqual(len(app.exception), 0)
        self.temperature.predict.assert_not_called()
        self.assertEqual(self.power.predict.call_args.args[0].MODULE_TEMPERATURE.iloc[0], 38.5)

    def test_completed_manual_prediction_saves_to_account(self):
        with patch.object(manual_pred, "save_prediction", return_value=True) as save:
            app = AppTest.from_string(
                "from manual_pred import render_manual_prediction\n"
                "render_manual_prediction('account store')"
            ).run()
            save.assert_not_called()
            app.date_input(key="manual_date").set_value(date(2024, 1, 15))
            app.button(key="manual_prediction_button").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(save.call_args.args, ("account store",))
            self.assertEqual(save.call_args.kwargs["source"], "Manual prediction")
            self.assertEqual(save.call_args.kwargs["predicted_for"].isoformat(), "2024-01-15T12:00:00+08:00")
            self.assertEqual(save.call_args.kwargs["power"], 500.)
            self.assertIn("Saved to your account.", [caption.value for caption in app.caption])

    def test_negative_and_invalid_model_outputs(self):
        for output in (-10., float("nan")):
            self.power.predict.reset_mock()
            self.power.predict.return_value = [output]
            app = self.app()
            app.button(key="manual_prediction_button").click().run()
            self.assertEqual(len(app.exception), 0)
            if output == -10.:
                self.assertEqual(app.metric[0].value, "0.00")
            else:
                self.assertEqual(len(app.metric), 0)
                self.assertIn("Unable to calculate", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
