import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).with_name("destructive_command_guard.py")
spec = importlib.util.spec_from_file_location("guard", MODULE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

class GuardTests(unittest.TestCase):
    def assertBlocked(self, command):
        self.assertIsNotNone(guard.reason_for(command), command)
    def assertAllowed(self, command):
        self.assertIsNone(guard.reason_for(command), command)

    def test_required_blocks(self):
        for command in [
            "rm -rf /tmp/demo", "rm -fr build", "rm --recursive --force dist",
            "psql -c 'DROP TABLE users'", "git push --force origin main",
            "git push -f origin main", "TRUNCATE TABLE sessions",
            "DELETE FROM users;", "delete from users",
        ]:
            with self.subTest(command=command): self.assertBlocked(command)

    def test_delete_with_where_allowed(self):
        self.assertAllowed("DELETE FROM users WHERE id = 42;")

    def test_normal_commands_allowed(self):
        for command in ["rm file.txt", "git push origin main", "git status",
                        "SELECT * FROM users", "echo 'DROP DATABASE is text'"]:
            with self.subTest(command=command): self.assertAllowed(command)

if __name__ == "__main__":
    unittest.main()
