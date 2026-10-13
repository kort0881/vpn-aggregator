import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    import pipeline
    import cli
    import scripts.parser
    import scripts.enricher
    import scripts.filters
    import scripts.profiler
    import scripts.repacker
    import scripts.reporter
    assert True