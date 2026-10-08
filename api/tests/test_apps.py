import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class SilkFlagTestCase(SimpleTestCase):
    # `SILK_ENABLED` is read once, when settings are imported, so each case needs a fresh process
    def _check(self, enable_silk: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=settings.BASE_DIR,
            env={**os.environ, "APP_ENABLE_SILK": enable_silk},
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_starts_with_silk_disabled(self):
        result = self._check("false")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_starts_with_silk_enabled(self):
        result = self._check("true")
        self.assertEqual(result.returncode, 0, result.stderr)
