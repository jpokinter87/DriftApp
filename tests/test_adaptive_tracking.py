"""
Tests pour le module core/tracking/adaptive_tracking.py

Ce module teste le système de suivi adaptatif à 3 modes.
"""

import pytest
from unittest.mock import MagicMock


class TestTrackingMode:
    """Tests pour l'enum TrackingMode."""

    def test_modes_disponibles(self):
        """Vérifie que les 4 modes existent."""
        from core.tracking.adaptive_tracking import TrackingMode

        assert TrackingMode.NORMAL.value == "normal"
        assert TrackingMode.CRITICAL.value == "critical"
        assert TrackingMode.CONTINUOUS.value == "continuous"
        assert TrackingMode.FAST_TRACK.value == "fast_track"


class TestTrackingParameters:
    """Tests pour le dataclass TrackingParameters."""

    def test_creation_parametres(self):
        """Création de paramètres de suivi."""
        from core.tracking.adaptive_tracking import (
            TrackingMode, TrackingParameters
        )

        params = TrackingParameters(
            mode=TrackingMode.NORMAL,
            check_interval=60,
            correction_threshold=0.5,
            motor_delay=0.002,
            description="Test"
        )

        assert params.mode == TrackingMode.NORMAL
        assert params.check_interval == 60
        assert params.correction_threshold == 0.5
        assert params.motor_delay == 0.002
        assert params.description == "Test"


class TestAdaptiveTrackingManagerInit:
    """Tests pour l'initialisation du gestionnaire adaptatif."""

    def test_init_sans_config(self):
        """Initialisation avec valeurs par défaut."""
        from core.tracking.adaptive_tracking import (
            AdaptiveTrackingManager, TrackingMode
        )

        manager = AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)

        assert manager.base_interval == 60
        assert manager.base_threshold == 0.5
        assert manager.ALTITUDE_CRITICAL == 68.0
        assert manager.ALTITUDE_ZENITH == 75.0
        assert manager.MOVEMENT_CRITICAL == 30.0
        assert manager.MOVEMENT_EXTREME == 50.0
        assert manager.current_mode == TrackingMode.NORMAL

    def test_init_avec_config(self, adaptive_config):
        """Initialisation avec configuration injectée."""
        from core.tracking.adaptive_tracking import AdaptiveTrackingManager

        manager = AdaptiveTrackingManager(
            base_interval=60,
            base_threshold=0.5,
            adaptive_config=adaptive_config
        )

        assert manager.ALTITUDE_CRITICAL == 68.0
        assert manager.ALTITUDE_ZENITH == 75.0
        assert manager.CRITICAL_ZONE_1 is not None


class TestGetParams:
    """Tests pour les méthodes _get_*_params."""

    @pytest.fixture
    def manager(self):
        from core.tracking.adaptive_tracking import AdaptiveTrackingManager
        return AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)

    def test_get_normal_params(self, manager):
        """Paramètres du mode NORMAL."""
        from core.tracking.adaptive_tracking import TrackingMode

        params = manager._get_normal_params()

        assert params.mode == TrackingMode.NORMAL
        assert params.check_interval == 60
        assert params.correction_threshold == 0.5
        assert params.motor_delay == 0.002

    def test_get_critical_params(self, manager):
        """Paramètres du mode CRITICAL."""
        from core.tracking.adaptive_tracking import TrackingMode

        params = manager._get_critical_params()

        assert params.mode == TrackingMode.CRITICAL
        assert params.check_interval == 15
        assert params.motor_delay == 0.001

    def test_get_continuous_params(self, manager):
        """Paramètres du mode CONTINUOUS."""
        from core.tracking.adaptive_tracking import TrackingMode

        params = manager._get_continuous_params()

        assert params.mode == TrackingMode.CONTINUOUS
        assert params.check_interval == 5
        assert params.correction_threshold == 0.1

    def test_get_fast_track_params(self, manager):
        """Paramètres du mode FAST_TRACK."""
        from core.tracking.adaptive_tracking import TrackingMode

        params = manager._get_fast_track_params()

        assert params.mode == TrackingMode.FAST_TRACK
        assert params.check_interval == 5


class TestPredicats:
    """Tests pour les prédicats d'évaluation."""

    @pytest.fixture
    def manager(self, adaptive_config):
        from core.tracking.adaptive_tracking import AdaptiveTrackingManager
        return AdaptiveTrackingManager(
            base_interval=60,
            base_threshold=0.5,
            adaptive_config=adaptive_config
        )

    def test_get_altitude_level_normal(self, manager):
        """Altitude normale (< 68°)."""
        assert manager._get_altitude_level(45.0) == "normal"
        assert manager._get_altitude_level(67.9) == "normal"

    def test_get_altitude_level_critical(self, manager):
        """Altitude critique (68-75°)."""
        assert manager._get_altitude_level(68.0) == "critical"
        assert manager._get_altitude_level(74.9) == "critical"

    def test_get_altitude_level_zenith(self, manager):
        """Altitude zénith (>= 75°)."""
        assert manager._get_altitude_level(75.0) == "zenith"
        assert manager._get_altitude_level(89.0) == "zenith"

    def test_get_movement_level_normal(self, manager):
        """Mouvement normal (< 30°)."""
        assert manager._get_movement_level(10.0) == "normal"
        assert manager._get_movement_level(29.9) == "normal"

    def test_get_movement_level_critical(self, manager):
        """Mouvement critique (30-50°)."""
        assert manager._get_movement_level(30.0) == "critical"
        assert manager._get_movement_level(49.9) == "critical"

    def test_get_movement_level_extreme(self, manager):
        """Mouvement extrême (>= 50°)."""
        assert manager._get_movement_level(50.0) == "extreme"
        assert manager._get_movement_level(100.0) == "extreme"

    def test_has_significant_movement(self, manager):
        """Test du mouvement significatif."""
        assert manager._has_significant_movement(2.0) is True
        assert manager._has_significant_movement(0.5) is False

    def test_is_in_critical_zone(self, manager):
        """Test de détection de zone critique."""
        # Dans la zone (alt: 65-80, az: 45-75)
        assert manager._is_in_critical_zone(70.0, 60.0) is True
        # Hors zone
        assert manager._is_in_critical_zone(50.0, 60.0) is False
        assert manager._is_in_critical_zone(70.0, 100.0) is False


class TestDecideMode:
    """Tests pour la décision de mode."""

    @pytest.fixture
    def manager(self):
        from core.tracking.adaptive_tracking import AdaptiveTrackingManager
        return AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)

    def test_mode_normal_conditions_standard(self, manager):
        """Mode NORMAL en conditions standard."""
        from core.tracking.adaptive_tracking import TrackingMode

        mode, reasons = manager._decide_mode(
            altitude_level="normal",
            movement_level="normal",
            in_critical_zone=False,
            altitude=45.0,
            delta=5.0
        )

        assert mode == TrackingMode.NORMAL
        assert "Conditions normales" in reasons[0]

    def test_mode_critical_altitude_critique(self, manager):
        """Mode CRITICAL pour altitude critique."""
        from core.tracking.adaptive_tracking import TrackingMode

        mode, reasons = manager._decide_mode(
            altitude_level="critical",
            movement_level="normal",
            in_critical_zone=False,
            altitude=70.0,
            delta=5.0
        )

        assert mode == TrackingMode.CRITICAL

    def test_mode_critical_mouvement_critique(self, manager):
        """Mode CRITICAL pour mouvement critique."""
        from core.tracking.adaptive_tracking import TrackingMode

        mode, reasons = manager._decide_mode(
            altitude_level="normal",
            movement_level="critical",
            in_critical_zone=False,
            altitude=45.0,
            delta=35.0
        )

        assert mode == TrackingMode.CRITICAL

    def test_mode_critical_grand_deplacement(self, manager):
        """Mode CRITICAL pour grand déplacement (>30°)."""
        from core.tracking.adaptive_tracking import TrackingMode

        mode, reasons = manager._decide_mode(
            altitude_level="normal",
            movement_level="critical",
            in_critical_zone=False,
            altitude=45.0,
            delta=35.0
        )

        assert mode == TrackingMode.CRITICAL

    def test_mode_continuous_mouvement_extreme(self, manager):
        """Mode CONTINUOUS pour mouvement extrême."""
        from core.tracking.adaptive_tracking import TrackingMode

        mode, reasons = manager._decide_mode(
            altitude_level="normal",
            movement_level="extreme",
            in_critical_zone=False,
            altitude=45.0,
            delta=60.0
        )

        assert mode == TrackingMode.CONTINUOUS

    def test_mode_continuous_zenith_avec_mouvement(self, manager):
        """Mode CONTINUOUS au zénith avec mouvement significatif."""
        from core.tracking.adaptive_tracking import TrackingMode

        mode, reasons = manager._decide_mode(
            altitude_level="zenith",
            movement_level="normal",
            in_critical_zone=False,
            altitude=78.0,
            delta=2.0  # > 1.0, mouvement significatif
        )

        assert mode == TrackingMode.CONTINUOUS

    def test_mode_critical_zenith_sans_mouvement(self, manager):
        """Mode CRITICAL au zénith SANS mouvement significatif."""
        from core.tracking.adaptive_tracking import TrackingMode

        mode, reasons = manager._decide_mode(
            altitude_level="zenith",
            movement_level="normal",
            in_critical_zone=False,
            altitude=78.0,
            delta=0.5  # < 1.0, mouvement faible
        )

        assert mode == TrackingMode.CRITICAL


class TestEvaluateTrackingZone:
    """Tests pour evaluate_tracking_zone."""

    @pytest.fixture
    def manager(self):
        from core.tracking.adaptive_tracking import AdaptiveTrackingManager
        return AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)

    def test_evaluate_retourne_parametres(self, manager):
        """Retourne des TrackingParameters valides."""
        from core.tracking.adaptive_tracking import TrackingParameters

        params = manager.evaluate_tracking_zone(
            altitude=45.0,
            azimut=120.0,
            delta_required=2.0
        )

        assert isinstance(params, TrackingParameters)

    def test_evaluate_change_mode_interne(self, manager):
        """Le mode courant est mis à jour."""
        from core.tracking.adaptive_tracking import TrackingMode

        # Commencer en NORMAL
        assert manager.current_mode == TrackingMode.NORMAL

        # Évaluer une zone critique
        manager.evaluate_tracking_zone(
            altitude=70.0,  # Altitude critique
            azimut=120.0,
            delta_required=2.0
        )

        assert manager.current_mode == TrackingMode.CRITICAL

    def test_evaluate_scenarios_complets(self, manager):
        """Test de scénarios complets."""
        from core.tracking.adaptive_tracking import TrackingMode

        scenarios = [
            # (altitude, azimut, delta, mode_attendu)
            (45.0, 120.0, 0.3, TrackingMode.NORMAL),
            (69.0, 60.0, 2.0, TrackingMode.CRITICAL),
            (76.0, 180.0, 5.0, TrackingMode.CONTINUOUS),
            (50.0, 100.0, 55.0, TrackingMode.CONTINUOUS),  # Mouvement extrême
        ]

        for alt, az, delta, expected_mode in scenarios:
            params = manager.evaluate_tracking_zone(alt, az, delta)
            assert params.mode == expected_mode, \
                f"Alt={alt}, Delta={delta}: attendu {expected_mode}, obtenu {params.mode}"


class TestVerifyShortestPath:
    """Tests pour verify_shortest_path."""

    @pytest.fixture
    def manager(self):
        from core.tracking.adaptive_tracking import AdaptiveTrackingManager
        return AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)

    def test_chemin_direct_positif(self, manager):
        """Chemin direct dans le sens horaire."""
        delta, desc = manager.verify_shortest_path(10.0, 50.0)

        assert delta == pytest.approx(40.0)
        assert "horaire" in desc

    def test_chemin_direct_negatif(self, manager):
        """Chemin direct dans le sens anti-horaire."""
        delta, desc = manager.verify_shortest_path(50.0, 10.0)

        assert delta == pytest.approx(-40.0)
        assert "anti-horaire" in desc

    def test_traversee_zero_horaire(self, manager):
        """Traversée de 0° dans le sens horaire."""
        delta, desc = manager.verify_shortest_path(350.0, 10.0)

        assert delta == pytest.approx(20.0)
        assert "horaire" in desc

    def test_traversee_zero_antihoraire(self, manager):
        """Traversée de 0° dans le sens anti-horaire."""
        delta, desc = manager.verify_shortest_path(10.0, 350.0)

        assert delta == pytest.approx(-20.0)
        assert "anti-horaire" in desc

    def test_chemin_long_vs_court(self, manager):
        """Choisit le chemin le plus court."""
        # De 10° à 300°: chemin court = -70°, pas +290°
        delta, desc = manager.verify_shortest_path(10.0, 300.0)

        assert abs(delta) == pytest.approx(70.0)
        assert delta < 0  # Anti-horaire est plus court

    def test_angle_180_ambigu(self, manager):
        """Cas ambigu à 180°."""
        delta, desc = manager.verify_shortest_path(0.0, 180.0)

        assert abs(delta) == pytest.approx(180.0)


class TestGetDiagnosticInfo:
    """Tests pour get_diagnostic_info."""

    @pytest.fixture
    def manager(self, adaptive_config):
        from core.tracking.adaptive_tracking import AdaptiveTrackingManager
        return AdaptiveTrackingManager(
            base_interval=60,
            base_threshold=0.5,
            adaptive_config=adaptive_config
        )

    def test_diagnostic_contient_cles(self, manager):
        """Le diagnostic contient toutes les clés attendues."""
        # D'abord évaluer pour initialiser current_params
        manager.evaluate_tracking_zone(45.0, 120.0, 2.0)

        info = manager.get_diagnostic_info(45.0, 120.0, 2.0)

        expected_keys = [
            'mode', 'mode_description', 'check_interval',
            'correction_threshold', 'motor_delay',
            'in_critical_zone', 'is_high_altitude', 'is_large_movement',
            'altitude_level', 'movement_level'
        ]
        for key in expected_keys:
            assert key in info

    def test_diagnostic_altitude_level(self, manager):
        """Niveau d'altitude correct dans le diagnostic."""
        manager.evaluate_tracking_zone(80.0, 120.0, 2.0)
        info = manager.get_diagnostic_info(80.0, 120.0, 2.0)

        assert info['altitude_level'] == "zenith"

    def test_diagnostic_movement_level(self, manager):
        """Niveau de mouvement correct dans le diagnostic."""
        manager.evaluate_tracking_zone(45.0, 120.0, 55.0)
        info = manager.get_diagnostic_info(45.0, 120.0, 55.0)

        assert info['movement_level'] == "extreme"


class TestModeTransitions:
    """Tests pour les transitions de mode."""

    def test_transition_normal_vers_critical(self):
        """Transition de NORMAL vers CRITICAL."""
        from core.tracking.adaptive_tracking import (
            AdaptiveTrackingManager, TrackingMode
        )

        manager = AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)
        assert manager.current_mode == TrackingMode.NORMAL

        # Passer en altitude critique
        params = manager.evaluate_tracking_zone(70.0, 120.0, 2.0)
        assert params.mode == TrackingMode.CRITICAL
        assert manager.current_mode == TrackingMode.CRITICAL

    def test_transition_critical_vers_continuous(self):
        """Transition de CRITICAL vers CONTINUOUS."""
        from core.tracking.adaptive_tracking import (
            AdaptiveTrackingManager, TrackingMode
        )

        manager = AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)

        # D'abord en CRITICAL
        manager.evaluate_tracking_zone(70.0, 120.0, 2.0)
        assert manager.current_mode == TrackingMode.CRITICAL

        # Puis mouvement extrême → CONTINUOUS
        params = manager.evaluate_tracking_zone(70.0, 120.0, 55.0)
        assert params.mode == TrackingMode.CONTINUOUS

    def test_retour_en_normal(self):
        """Retour au mode NORMAL."""
        from core.tracking.adaptive_tracking import (
            AdaptiveTrackingManager, TrackingMode
        )

        manager = AdaptiveTrackingManager(base_interval=60, base_threshold=0.5)

        # Passer en CRITICAL
        manager.evaluate_tracking_zone(70.0, 120.0, 2.0)
        assert manager.current_mode == TrackingMode.CRITICAL

        # Retour en conditions normales
        params = manager.evaluate_tracking_zone(45.0, 120.0, 2.0)
        assert params.mode == TrackingMode.NORMAL
        assert manager.current_mode == TrackingMode.NORMAL
