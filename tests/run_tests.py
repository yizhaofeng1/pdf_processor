"""Test runner script for ExamSplit AI unit tests."""

import sys
import pytest

if __name__ == "__main__":
    args = ["-v", "tests/unit/test_batch_basket_and_templates.py"]
    ret = pytest.main(args)
    sys.exit(ret)
