import unittest
from email_filter import commands, validate_flags

class TestCommandLineFlags(unittest.TestCase):

    def test_valid_flags(self):
        # Test valid flags for 'cycle' command
        result = validate_flags('cycle', {'command': 'cycle'}, ['-size', '50'])
        self.assertEqual(result, True)

        # Test valid flags for 'range' command
        result = validate_flags('range', {'command': 'range'}, ['-from', '10', '-to', '20'])
        self.assertEqual(result, True)

    def test_invalid_flags(self):
        # Test invalid flags for 'cycle' command
        result = validate_flags('cycle', {'command': 'cycle'}, ['-invalid_flag', '50'])
        self.assertEqual(result, False)

        # Test invalid flags for 'range' command
        result = validate_flags('range', {'command': 'range'}, ['-invalid_flag', '10'])
        self.assertEqual(result, False)


if __name__ == '__main__':
    unittest.main()
