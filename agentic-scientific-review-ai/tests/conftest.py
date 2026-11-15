from pathlib import Path
import pytest
from reviewai.config import Settings
from reviewai.pipeline import ReviewEngine

@pytest.fixture
def engine(tmp_path):
    return ReviewEngine(Settings(data_dir=tmp_path,gemini_key="",max_papers=12))

@pytest.fixture
def demo_state(engine):
    prepared=engine.prepare("Scalable lakehouse architectures for big data analytics","demo")
    return engine.continue_review(prepared["run_id"],approve=True)
