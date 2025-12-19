"""
Fixtures partagées pour les tests DriftApp.

Ce fichier contient les fixtures pytest utilisées par plusieurs fichiers de test.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# FIXTURES CONFIGURATION
# =============================================================================

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Configuration de test minimale."""
    return {
        "site": {
            "latitude": 44.15,
            "longitude": 5.23,
            "tz_offset": 1,
            "encoder_mode": "relative",
            "simulation": True
        },
        "motor": {
            "steps_per_revolution": 200,
            "microstepping": 4,
            "gear_ratio": 2230.0
        },
        "gpio": {
            "dir_pin": 17,
            "step_pin": 18,
            "ms1_pin": 27,
            "ms2_pin": 22
        },
        "dome_offsets": {
            "meridian_offset": 180.0,
            "zenith_offset": 180.0
        }
    }


@pytest.fixture
def temp_config_file(sample_config, tmp_path) -> Path:
    """Crée un fichier config.json temporaire."""
    config_file = tmp_path / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(sample_config, f)
    return config_file


@pytest.fixture
def adaptive_config():
    """Configuration adaptive tracking simulée."""
    class MockModeConfig:
        def __init__(self, interval, threshold, delay):
            self.interval_sec = interval
            self.threshold_deg = threshold
            self.motor_delay = delay

    class MockModes:
        def get(self, mode_name):
            modes = {
                'normal': MockModeConfig(60, 0.5, 0.002),
                'critical': MockModeConfig(15, 0.25, 0.001),
                'continuous': MockModeConfig(5, 0.1, 0.0001),
                'fast_track': MockModeConfig(5, 0.5, 0.0002)
            }
            return modes.get(mode_name)

    class MockAltitudes:
        critical = 68.0
        zenith = 75.0

    class MockMovements:
        critical = 30.0
        extreme = 50.0
        min_for_continuous = 1.0

    class MockCriticalZone:
        alt_min = 65.0
        alt_max = 80.0
        az_min = 45.0
        az_max = 75.0
        name = "Zone Test"
        enabled = True

    class MockAdaptiveConfig:
        altitudes = MockAltitudes()
        movements = MockMovements()
        critical_zones = [MockCriticalZone()]
        modes = MockModes()

    return MockAdaptiveConfig()


# =============================================================================
# FIXTURES ASTRONOMIQUES
# =============================================================================

@pytest.fixture
def observation_datetime() -> datetime:
    """Date/heure d'observation fixe pour tests reproductibles."""
    return datetime(2025, 6, 21, 22, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def known_objects() -> Dict[str, Dict[str, float]]:
    """Objets célestes avec coordonnées connues pour tests."""
    return {
        "M13": {
            "ra_deg": 250.42,
            "dec_deg": 36.46,
            "description": "Amas globulaire d'Hercule"
        },
        "Vega": {
            "ra_deg": 279.23,
            "dec_deg": 38.78,
            "description": "Etoile brillante de la Lyre"
        },
        "Polaris": {
            "ra_deg": 37.95,
            "dec_deg": 89.26,
            "description": "Etoile polaire"
        },
        "NGC6826": {
            "ra_deg": 296.20,
            "dec_deg": 50.53,
            "description": "Nebuleuse du Clin d'Oeil"
        }
    }


@pytest.fixture
def site_location() -> Dict[str, float]:
    """Coordonnées du site d'observation."""
    return {
        "latitude": 44.15,
        "longitude": 5.23,
        "altitude_m": 800,
        "tz_offset": 1
    }


# =============================================================================
# FIXTURES ABAQUE
# =============================================================================

@pytest.fixture
def sample_abaque_data() -> Dict[float, Dict[str, list]]:
    """Données d'abaque simulées pour tests."""
    return {
        30.0: {
            'az_astre': [0, 45, 90, 135, 180, 225, 270, 315],
            'az_coupole': [2, 47, 95, 138, 182, 227, 272, 317]
        },
        45.0: {
            'az_astre': [0, 45, 90, 135, 180, 225, 270, 315],
            'az_coupole': [3, 48, 96, 139, 183, 228, 273, 318]
        },
        60.0: {
            'az_astre': [0, 45, 90, 135, 180, 225, 270, 315],
            'az_coupole': [4, 49, 97, 140, 184, 229, 274, 319]
        },
        75.0: {
            'az_astre': [0, 45, 90, 135, 180, 225, 270, 315],
            'az_coupole': [5, 50, 98, 141, 185, 230, 275, 320]
        }
    }


# =============================================================================
# FIXTURES HARDWARE (MOCKS)
# =============================================================================

@pytest.fixture
def mock_gpio():
    """Mock pour les bibliothèques GPIO."""
    with patch.dict('sys.modules', {
        'RPi': MagicMock(),
        'RPi.GPIO': MagicMock(),
        'lgpio': MagicMock(),
        'spidev': MagicMock()
    }):
        yield


@pytest.fixture
def mock_daemon_encoder_data() -> Dict[str, Any]:
    """Données simulées du daemon encodeur."""
    return {
        "angle": 45.5,
        "raw": 512,
        "total_counts": 47104,
        "timestamp": "2025-06-21T22:00:00",
        "age_ms": 10,
        "calibrated": True
    }


@pytest.fixture
def mock_encoder_json_file(mock_daemon_encoder_data, tmp_path) -> Path:
    """Crée un fichier JSON daemon simulé."""
    json_file = tmp_path / "ems22_position.json"
    with open(json_file, "w") as f:
        json.dump(mock_daemon_encoder_data, f)
    return json_file


# =============================================================================
# FIXTURES MOTEUR
# =============================================================================

@pytest.fixture
def motor_config() -> Dict[str, Any]:
    """Configuration moteur pour tests."""
    return {
        "steps_per_revolution": 200,
        "microstepping": 4,
        "gear_ratio": 2230.0,
        "steps_correction_factor": 1.08849,
        "dir_pin": 17,
        "step_pin": 18,
        "min_delay": 0.00005,  # 50 microseconds
        "max_delay": 0.01      # 10 milliseconds
    }


# =============================================================================
# HELPERS
# =============================================================================

def approx_angle(expected: float, rel: float = 1e-3, abs: float = 0.01):
    """Helper pour comparaison d'angles avec tolérance."""
    return pytest.approx(expected, rel=rel, abs=abs)
