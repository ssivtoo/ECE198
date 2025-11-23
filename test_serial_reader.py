import unittest
from unittest.mock import MagicMock
import sys

# Mock serial module
sys.modules['serial'] = MagicMock()

from SerialReader import parse_line, interpret

class TestSerialReader(unittest.TestCase):
    def test_parse_line_valid(self):
        line = "500,300,150.5"
        result = parse_line(line)
        self.assertEqual(result, (500, 300, 150.5))

    def test_parse_line_invalid_length(self):
        line = "500,300"
        result = parse_line(line)
        self.assertIsNone(result)

    def test_parse_line_invalid_format(self):
        line = "500,abc,150.5"
        result = parse_line(line)
        self.assertIsNone(result)

    def test_interpret_empty(self):
        msg = interpret(100, 100, 5.0)
        self.assertIn("Empty", msg)
        self.assertIn("Dark", msg)
        self.assertIn("Quiet", msg)

    def test_interpret_full(self):
        msg = interpret(800, 800, 500.0)
        self.assertIn("Full", msg)
        self.assertIn("Bright", msg)
        self.assertIn("Loud", msg)

if __name__ == '__main__':
    unittest.main()
