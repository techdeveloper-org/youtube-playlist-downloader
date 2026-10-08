"""Unit tests for validating launcher scripts staticaly via AST."""
import ast
import os
import unittest

class TestLaunchers(unittest.TestCase):
    """Ensure launcher scripts bind to root modules properly."""
    
    def setUp(self):
        """Find project root."""
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_run_gui_ast(self):
        """Validate run_gui.py imports gui.main."""
        path = os.path.join(self.repo_root, "run_gui.py")
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        
        has_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "main" and any(n.name == "main" for n in node.names):
                    has_import = True
        self.assertTrue(has_import)

    def test_run_youtube_downloader_ast(self):
        """Validate run_youtube_downloader.py imports main.main."""
        path = os.path.join(self.repo_root, "run_youtube_downloader.py")
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        
        has_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "main" and any(n.name == "main" for n in node.names):
                    has_import = True
        self.assertTrue(has_import)
