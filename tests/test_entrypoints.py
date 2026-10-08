"""Unit tests for validating console script entrypoints."""
import unittest

class TestEntrypoints(unittest.TestCase):
    """Verify callables for project.scripts."""

    def test_main_callable(self):
        """Ensure main function in main is callable."""
        import main
        self.assertTrue(callable(main.main))

    def skip_test_gui_callable(self):
        """Ensure main function in gui is callable."""
        import gui
        self.assertTrue(callable(gui.main))
