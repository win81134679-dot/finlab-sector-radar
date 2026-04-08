"""tests/test_config.py — config.py 單元測試"""
import os
from pathlib import Path
from unittest.mock import patch


def test_base_dir_points_to_project_root():
    from src.config import BASE_DIR
    assert BASE_DIR.is_dir()
    assert (BASE_DIR / "src").is_dir()


def test_output_dir_exists():
    from src.config import OUTPUT_DIR
    assert OUTPUT_DIR.is_dir()


def test_cache_dir_exists():
    from src.config import CACHE_DIR
    assert CACHE_DIR.is_dir()


def test_is_finlab_token_set_false_when_empty():
    with patch.dict(os.environ, {"FINLAB_API_TOKEN": ""}):
        # Re-import to pick up env var
        import importlib
        import src.config as cfg
        importlib.reload(cfg)
        assert cfg.is_finlab_token_set() is False


def test_is_fred_key_set_false_when_empty():
    with patch.dict(os.environ, {"FRED_API_KEY": ""}):
        import importlib
        import src.config as cfg
        importlib.reload(cfg)
        assert cfg.is_fred_key_set() is False


def test_is_av_key_set_false_when_empty():
    with patch.dict(os.environ, {"ALPHA_VANTAGE_KEY": ""}):
        import importlib
        import src.config as cfg
        importlib.reload(cfg)
        assert cfg.is_av_key_set() is False


def test_is_discord_configured_false_when_all_empty():
    envs = {
        "DISCORD_WEBHOOK_DAILY": "",
        "DISCORD_WEBHOOK_ALERT": "",
        "DISCORD_WEBHOOK_MACRO": "",
        "DISCORD_WEBHOOK_SYSTEM": "",
    }
    with patch.dict(os.environ, envs):
        import importlib
        import src.config as cfg
        importlib.reload(cfg)
        assert cfg.is_discord_configured() is False


def test_default_constants():
    from src.config import (
        RS_LOOKBACK_DAYS,
        REVENUE_CONSECUTIVE_MONTHS,
        TECHNICAL_MA_LONG,
        TECHNICAL_MA_SHORT,
    )
    assert RS_LOOKBACK_DAYS == 60
    assert REVENUE_CONSECUTIVE_MONTHS == 3
    assert TECHNICAL_MA_LONG == 60
    assert TECHNICAL_MA_SHORT == 20


def test_custom_sectors_csv_path():
    from src.config import CUSTOM_SECTORS_CSV
    assert CUSTOM_SECTORS_CSV.name == "custom_sectors.csv"
