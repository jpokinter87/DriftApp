"""
Tests pour le module core/hardware/moteur.py

Ce module teste le contrôleur moteur avec des mocks GPIO.
"""

import json
import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, Any


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_lgpio():
    """Mock complet pour lgpio."""
    mock = MagicMock()
    mock.gpiochip_open.return_value = 1
    mock.gpio_claim_output.return_value = None
    mock.gpio_write.return_value = None
    mock.gpio_free.return_value = None
    mock.gpiochip_close.return_value = None
    return mock


@pytest.fixture
def motor_config_dict() -> Dict[str, Any]:
    """Configuration moteur en format dict."""
    return {
        'gpio_pins': {
            'dir': 17,
            'step': 18
        },
        'steps_per_revolution': 200,
        'microsteps': 4,
        'gear_ratio': 2230.0,
        'steps_correction_factor': 1.08849
    }


@pytest.fixture
def motor_config_dataclass():
    """Configuration moteur en format dataclass."""
    class GpioPins:
        dir = 17
        step = 18

    class MotorConfig:
        gpio_pins = GpioPins()
        steps_per_revolution = 200
        microsteps = 4
        gear_ratio = 2230.0
        steps_correction_factor = 1.08849

    return MotorConfig()


# =============================================================================
# TESTS DAEMONENCODERREADER
# =============================================================================

class TestDaemonEncoderReader:
    """Tests pour DaemonEncoderReader."""

    def test_init_chemin_defaut(self):
        """Initialisation avec chemin par défaut."""
        # Importer avec mocks GPIO
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader, DAEMON_JSON

            reader = DaemonEncoderReader()
            assert reader.daemon_path == DAEMON_JSON

    def test_init_chemin_personnalise(self):
        """Initialisation avec chemin personnalisé."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            custom_path = Path("/custom/path.json")
            reader = DaemonEncoderReader(custom_path)
            assert reader.daemon_path == custom_path

    def test_is_available_false(self):
        """is_available retourne False si fichier n'existe pas."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            reader = DaemonEncoderReader(Path("/inexistant/path.json"))
            assert reader.is_available() is False

    def test_is_available_true(self, tmp_path):
        """is_available retourne True si fichier existe."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            json_file = tmp_path / "test.json"
            json_file.write_text('{"angle": 45.0}')

            reader = DaemonEncoderReader(json_file)
            assert reader.is_available() is True

    def test_read_raw_fichier_valide(self, tmp_path):
        """Lecture brute d'un fichier JSON valide."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            json_file = tmp_path / "test.json"
            data = {"angle": 45.5, "status": "OK", "calibrated": True}
            json_file.write_text(json.dumps(data))

            reader = DaemonEncoderReader(json_file)
            result = reader.read_raw()

            assert result == data

    def test_read_raw_fichier_inexistant(self):
        """Lecture brute retourne None si fichier n'existe pas."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            reader = DaemonEncoderReader(Path("/inexistant.json"))
            result = reader.read_raw()

            assert result is None

    def test_read_raw_json_invalide(self, tmp_path):
        """Lecture brute retourne None si JSON invalide."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            json_file = tmp_path / "invalid.json"
            json_file.write_text("{ invalid json }")

            reader = DaemonEncoderReader(json_file)
            result = reader.read_raw()

            assert result is None

    def test_read_angle_success(self, tmp_path):
        """Lecture de l'angle avec succès."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            json_file = tmp_path / "test.json"
            data = {"angle": 123.45, "status": "OK"}
            json_file.write_text(json.dumps(data))

            reader = DaemonEncoderReader(json_file)
            result = reader.read_angle(timeout_ms=100)

            assert result == pytest.approx(123.45)

    def test_read_angle_normalise_360(self, tmp_path):
        """L'angle est normalisé dans [0, 360)."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            json_file = tmp_path / "test.json"
            data = {"angle": 370.0, "status": "OK"}
            json_file.write_text(json.dumps(data))

            reader = DaemonEncoderReader(json_file)
            result = reader.read_angle()

            assert result == pytest.approx(10.0)

    def test_read_angle_timeout(self):
        """Timeout si fichier non trouvé."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            reader = DaemonEncoderReader(Path("/inexistant.json"))

            with pytest.raises(RuntimeError, match="non trouvé"):
                reader.read_angle(timeout_ms=50)

    def test_read_status(self, tmp_path):
        """Lecture du statut complet."""
        with patch.dict('sys.modules', {'lgpio': MagicMock(), 'RPi': MagicMock(), 'RPi.GPIO': MagicMock()}):
            from core.hardware.moteur import DaemonEncoderReader

            json_file = tmp_path / "test.json"
            data = {"angle": 45.0, "status": "OK", "calibrated": True, "raw": 512}
            json_file.write_text(json.dumps(data))

            reader = DaemonEncoderReader(json_file)
            result = reader.read_status()

            assert result == data


# =============================================================================
# TESTS MOTEURCOUPOLE - CONFIGURATION
# =============================================================================

class TestMoteurCoupoleConfig:
    """Tests pour la configuration du moteur."""

    def test_charger_config_dict(self, motor_config_dict, mock_lgpio):
        """Charge la configuration depuis un dict."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                # Contourner l'init complet
                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                moteur._charger_config(motor_config_dict)

                assert moteur.DIR == 17
                assert moteur.STEP == 18
                assert moteur.STEPS_PER_REV == 200
                assert moteur.MICROSTEPS == 4
                assert moteur.gear_ratio == 2230.0

    def test_charger_config_dataclass(self, motor_config_dataclass, mock_lgpio):
        """Charge la configuration depuis une dataclass."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                moteur._charger_config(motor_config_dataclass)

                assert moteur.DIR == 17
                assert moteur.STEP == 18

    def test_valider_config_steps_invalide(self, mock_lgpio):
        """Lève une erreur si steps_per_revolution invalide."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                moteur.STEPS_PER_REV = 0
                moteur.MICROSTEPS = 4
                moteur.gear_ratio = 2230.0
                moteur.steps_correction_factor = 1.0

                with pytest.raises(ValueError, match="steps_per_revolution"):
                    moteur._valider_config()

    def test_valider_config_microsteps_invalide(self, mock_lgpio):
        """Lève une erreur si microsteps invalide."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                moteur.STEPS_PER_REV = 200
                moteur.MICROSTEPS = 5  # Invalide
                moteur.gear_ratio = 2230.0
                moteur.steps_correction_factor = 1.0

                with pytest.raises(ValueError, match="microsteps"):
                    moteur._valider_config()

    def test_calculer_steps_par_tour(self, mock_lgpio):
        """Calcul correct du nombre de pas par tour."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                moteur.STEPS_PER_REV = 200
                moteur.MICROSTEPS = 4
                moteur.gear_ratio = 2230.0
                moteur.steps_correction_factor = 1.08849

                moteur._calculer_steps_par_tour()

                # 200 * 4 * 2230 * 1.08849 ≈ 1,942,968
                expected = int(200 * 4 * 2230.0 * 1.08849)
                assert moteur.steps_per_dome_revolution == expected


# =============================================================================
# TESTS MOTEURCOUPOLE - CONTRÔLE MOTEUR
# =============================================================================

class TestMoteurCoupoleControl:
    """Tests pour le contrôle moteur."""

    @pytest.fixture
    def mock_moteur(self, motor_config_dict, mock_lgpio):
        """Crée un moteur mocké."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                moteur.gpio_lib = 'lgpio'
                moteur.gpio_handle = 1
                moteur._charger_config(motor_config_dict)
                moteur._calculer_steps_par_tour()
                moteur.direction_actuelle = 1
                moteur.stop_requested = False

                return moteur

    def test_valider_delai_normal(self, mock_moteur):
        """Délai normal reste inchangé."""
        result = mock_moteur._valider_delai(0.001)
        assert result == 0.001

    def test_valider_delai_trop_petit(self, mock_moteur):
        """Délai trop petit est corrigé."""
        result = mock_moteur._valider_delai(0.00001)
        assert result == 0.00005  # Minimum 50µs

    def test_definir_direction_positive(self, mock_moteur, mock_lgpio):
        """Direction positive (horaire)."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            mock_moteur._gpio_write = MagicMock()
            mock_moteur.definir_direction(1)

            assert mock_moteur.direction_actuelle == 1
            mock_moteur._gpio_write.assert_called_once()

    def test_definir_direction_negative(self, mock_moteur, mock_lgpio):
        """Direction négative (anti-horaire)."""
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            mock_moteur._gpio_write = MagicMock()
            mock_moteur.definir_direction(-1)

            assert mock_moteur.direction_actuelle == -1

    def test_rotation_zero_degres(self, mock_moteur):
        """Rotation de 0° ne fait rien."""
        mock_moteur.faire_un_pas = MagicMock()
        mock_moteur.definir_direction = MagicMock()

        mock_moteur.rotation(0.0, vitesse=0.001)

        mock_moteur.faire_un_pas.assert_not_called()

    def test_rotation_calcul_steps(self, mock_moteur):
        """Calcul correct du nombre de pas."""
        mock_moteur.faire_un_pas = MagicMock()
        mock_moteur.definir_direction = MagicMock()

        # Pour 1° avec steps_per_dome_revolution ≈ 1,942,968
        # deg_per_step = 360 / 1,942,968 ≈ 0.000185°
        # steps = 1 / 0.000185 ≈ 5,397
        mock_moteur.rotation(1.0, vitesse=0.001)

        expected_steps = int(1.0 / (360.0 / mock_moteur.steps_per_dome_revolution))
        assert mock_moteur.faire_un_pas.call_count == expected_steps

    def test_rotation_stop_requested(self, mock_moteur):
        """Arrêt si stop_requested est True."""
        mock_moteur.faire_un_pas = MagicMock()
        mock_moteur.definir_direction = MagicMock()

        # Simuler un arrêt après quelques pas
        call_count = [0]
        def side_effect(*args):
            call_count[0] += 1
            if call_count[0] >= 10:
                mock_moteur.stop_requested = True

        mock_moteur.faire_un_pas.side_effect = side_effect

        mock_moteur.rotation(1.0, vitesse=0.001)

        # Devrait s'arrêter bien avant le nombre total de pas
        assert mock_moteur.faire_un_pas.call_count < 100

    def test_request_stop(self, mock_moteur):
        """request_stop met le flag à True."""
        assert mock_moteur.stop_requested is False
        mock_moteur.request_stop()
        assert mock_moteur.stop_requested is True

    def test_clear_stop_request(self, mock_moteur):
        """clear_stop_request remet le flag à False."""
        mock_moteur.stop_requested = True
        mock_moteur.clear_stop_request()
        assert mock_moteur.stop_requested is False


class TestMoteurCoupoleAbsolute:
    """Tests pour rotation_absolue."""

    @pytest.fixture
    def mock_moteur(self, motor_config_dict, mock_lgpio):
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                moteur.gpio_lib = 'lgpio'
                moteur.gpio_handle = 1
                moteur._charger_config(motor_config_dict)
                moteur._calculer_steps_par_tour()
                moteur.direction_actuelle = 1
                moteur.stop_requested = False
                moteur.rotation = MagicMock()

                return moteur

    def test_rotation_absolue_chemin_court_positif(self, mock_moteur):
        """Chemin court positif (horaire)."""
        mock_moteur.rotation_absolue(100.0, 50.0)

        mock_moteur.rotation.assert_called_once()
        args = mock_moteur.rotation.call_args[0]
        assert args[0] == pytest.approx(50.0)

    def test_rotation_absolue_chemin_court_negatif(self, mock_moteur):
        """Chemin court négatif (anti-horaire)."""
        mock_moteur.rotation_absolue(50.0, 100.0)

        args = mock_moteur.rotation.call_args[0]
        assert args[0] == pytest.approx(-50.0)

    def test_rotation_absolue_traverse_zero(self, mock_moteur):
        """Traversée de 0° prend le chemin le plus court."""
        mock_moteur.rotation_absolue(10.0, 350.0)

        args = mock_moteur.rotation.call_args[0]
        assert args[0] == pytest.approx(20.0)  # +20° pas -340°

    def test_rotation_absolue_normalise_angles(self, mock_moteur):
        """Les angles sont normalisés."""
        mock_moteur.rotation_absolue(370.0, 10.0)  # 370 = 10

        args = mock_moteur.rotation.call_args[0]
        assert abs(args[0]) < 1.0  # Quasi nul


# =============================================================================
# TESTS MOTEURCOUPOLE - DÉLAI RAMPE
# =============================================================================

class TestMoteurCoupoleRampe:
    """Tests pour le calcul de délai (rampe désactivée)."""

    @pytest.fixture
    def mock_moteur(self, motor_config_dict, mock_lgpio):
        with patch.dict('sys.modules', {'lgpio': mock_lgpio}):
            with patch('core.hardware.moteur.GPIO_LIB', 'lgpio'):
                from core.hardware.moteur import MoteurCoupole

                moteur = object.__new__(MoteurCoupole)
                moteur.logger = MagicMock()
                return moteur

    def test_calculer_delai_rampe_constant(self, mock_moteur):
        """Délai constant (pas de rampe)."""
        vitesse_nominale = 0.001

        # Début, milieu, fin - tous doivent être constants
        delai_debut = mock_moteur._calculer_delai_rampe(0, 1000, vitesse_nominale)
        delai_milieu = mock_moteur._calculer_delai_rampe(500, 1000, vitesse_nominale)
        delai_fin = mock_moteur._calculer_delai_rampe(999, 1000, vitesse_nominale)

        assert delai_debut == vitesse_nominale
        assert delai_milieu == vitesse_nominale
        assert delai_fin == vitesse_nominale
