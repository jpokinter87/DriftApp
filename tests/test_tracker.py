"""
Tests pour le module core/tracking/tracker.py

Ce module teste le gestionnaire de session de suivi.
"""

import pytest
from datetime import datetime, timezone
from collections import deque
from unittest.mock import MagicMock, patch, PropertyMock


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_moteur():
    """Mock pour MoteurCoupole."""
    moteur = MagicMock()
    moteur.steps_per_dome_revolution = 1942968
    moteur.stop_requested = False
    moteur.rotation = MagicMock()
    moteur.rotation_avec_feedback = MagicMock(return_value={
        'success': True,
        'position_finale': 90.0,
        'erreur_finale': 0.1
    })
    moteur.request_stop = MagicMock()
    moteur.clear_stop_request = MagicMock()
    return moteur


@pytest.fixture
def mock_calc():
    """Mock pour AstronomicalCalculations."""
    calc = MagicMock()
    calc.latitude = 44.15
    calc.longitude = 5.23
    calc.tz_offset = 1
    calc.calculer_coords_horizontales.return_value = (120.0, 45.0)
    calc.calculer_coords_horizontales_coupole.return_value = (122.0, 45.0, 2.0)
    calc.convertir_j2000_vers_jnow.return_value = (250.0, 36.0)
    return calc


@pytest.fixture
def mock_tracking_logger():
    """Mock pour TrackingLogger."""
    logger = MagicMock()
    logger.log_correction = MagicMock()
    logger.log_session_start = MagicMock()
    logger.log_session_end = MagicMock()
    return logger


@pytest.fixture
def mock_abaque_manager():
    """Mock pour AbaqueManager."""
    manager = MagicMock()
    manager.load_abaque.return_value = True
    manager.is_loaded = True
    manager.get_dome_position.return_value = (125.0, {
        'method': 'interpolation',
        'in_bounds': True
    })
    return manager


@pytest.fixture
def mock_adaptive_manager():
    """Mock pour AdaptiveTrackingManager."""
    from core.tracking.adaptive_tracking import TrackingMode, TrackingParameters

    manager = MagicMock()
    manager.current_mode = TrackingMode.NORMAL
    manager.evaluate_tracking_zone.return_value = TrackingParameters(
        mode=TrackingMode.NORMAL,
        check_interval=60,
        correction_threshold=0.5,
        motor_delay=0.002,
        description="Test mode"
    )
    manager.verify_shortest_path.return_value = (5.0, "horaire (5.0°)")
    return manager


@pytest.fixture
def mock_encoder_config():
    """Mock pour encoder config."""
    config = MagicMock()
    config.enabled = False
    return config


@pytest.fixture
def mock_motor_config():
    """Mock pour motor config."""
    config = MagicMock()
    config.steps_correction_factor = 1.08849
    return config


# =============================================================================
# TESTS INITIALISATION
# =============================================================================

class TestTrackingSessionInit:
    """Tests pour l'initialisation de TrackingSession."""

    def test_init_sans_abaque_leve_erreur(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config
    ):
        """Lève ValueError si abaque_file non fourni."""
        with patch.dict('sys.modules', {
            'lgpio': MagicMock(),
            'RPi': MagicMock(),
            'RPi.GPIO': MagicMock()
        }):
            from core.tracking.tracker import TrackingSession

            with pytest.raises(ValueError, match="abaque_file requis"):
                TrackingSession(
                    moteur=mock_moteur,
                    calc=mock_calc,
                    logger=mock_tracking_logger,
                    abaque_file=None,
                    encoder_config=mock_encoder_config,
                    motor_config=mock_motor_config
                )

    @patch('core.tracking.tracker.AbaqueManager')
    @patch('core.tracking.tracker.AdaptiveTrackingManager')
    def test_init_avec_abaque_valide(
        self, mock_adaptive_cls, mock_abaque_cls,
        mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        """Initialisation réussie avec abaque valide."""
        mock_abaque_cls.return_value = mock_abaque_manager

        with patch.dict('sys.modules', {
            'lgpio': MagicMock(),
            'RPi': MagicMock(),
            'RPi.GPIO': MagicMock()
        }):
            from core.tracking.tracker import TrackingSession

            session = TrackingSession(
                moteur=mock_moteur,
                calc=mock_calc,
                logger=mock_tracking_logger,
                seuil=0.5,
                intervalle=60,
                abaque_file="data/Loi_coupole.xlsx",
                encoder_config=mock_encoder_config,
                motor_config=mock_motor_config
            )

            assert session.moteur == mock_moteur
            assert session.calc == mock_calc
            assert session.seuil == 0.5
            assert session.intervalle == 60
            assert session.running is False

    @patch('core.tracking.tracker.AbaqueManager')
    @patch('core.tracking.tracker.AdaptiveTrackingManager')
    def test_init_etat_initial(
        self, mock_adaptive_cls, mock_abaque_cls,
        mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        """Vérifie l'état initial après initialisation."""
        mock_abaque_cls.return_value = mock_abaque_manager

        with patch.dict('sys.modules', {
            'lgpio': MagicMock(),
            'RPi': MagicMock(),
            'RPi.GPIO': MagicMock()
        }):
            from core.tracking.tracker import TrackingSession

            session = TrackingSession(
                moteur=mock_moteur,
                calc=mock_calc,
                logger=mock_tracking_logger,
                abaque_file="data/Loi_coupole.xlsx",
                encoder_config=mock_encoder_config,
                motor_config=mock_motor_config
            )

            assert session.objet is None
            assert session.ra_deg is None
            assert session.dec_deg is None
            assert session.is_planet is False
            assert session.position_relative == 0.0
            assert session.total_corrections == 0
            assert session.total_movement == 0.0


# =============================================================================
# TESTS ENCODEUR
# =============================================================================

class TestTrackingSessionEncoder:
    """Tests pour la gestion de l'encodeur."""

    @patch('core.tracking.tracker.AbaqueManager')
    @patch('core.tracking.tracker.AdaptiveTrackingManager')
    @patch('core.tracking.tracker.HardwareDetector')
    def test_encoder_desactive(
        self, mock_hw_detector, mock_adaptive_cls, mock_abaque_cls,
        mock_moteur, mock_calc, mock_tracking_logger,
        mock_motor_config, mock_abaque_manager
    ):
        """Encodeur désactivé dans la config."""
        mock_abaque_cls.return_value = mock_abaque_manager

        encoder_config = MagicMock()
        encoder_config.enabled = False

        with patch.dict('sys.modules', {
            'lgpio': MagicMock(),
            'RPi': MagicMock(),
            'RPi.GPIO': MagicMock()
        }):
            from core.tracking.tracker import TrackingSession

            session = TrackingSession(
                moteur=mock_moteur,
                calc=mock_calc,
                logger=mock_tracking_logger,
                abaque_file="data/Loi_coupole.xlsx",
                encoder_config=encoder_config,
                motor_config=mock_motor_config
            )

            assert session.encoder_available is False

    @patch('core.tracking.tracker.AbaqueManager')
    @patch('core.tracking.tracker.AdaptiveTrackingManager')
    @patch('core.tracking.tracker.HardwareDetector')
    @patch('core.tracking.tracker.MoteurCoupole')
    def test_encoder_active_et_disponible(
        self, mock_moteur_cls, mock_hw_detector, mock_adaptive_cls, mock_abaque_cls,
        mock_moteur, mock_calc, mock_tracking_logger,
        mock_motor_config, mock_abaque_manager
    ):
        """Encodeur activé et daemon disponible."""
        mock_abaque_cls.return_value = mock_abaque_manager
        mock_hw_detector.check_encoder_daemon.return_value = (True, None, 45.0)
        mock_moteur_cls.get_daemon_angle.return_value = 45.0

        encoder_config = MagicMock()
        encoder_config.enabled = True

        with patch.dict('sys.modules', {
            'lgpio': MagicMock(),
            'RPi': MagicMock(),
            'RPi.GPIO': MagicMock()
        }):
            from core.tracking.tracker import TrackingSession

            session = TrackingSession(
                moteur=mock_moteur,
                calc=mock_calc,
                logger=mock_tracking_logger,
                abaque_file="data/Loi_coupole.xlsx",
                encoder_config=encoder_config,
                motor_config=mock_motor_config
            )

            assert session.encoder_available is True


# =============================================================================
# TESTS CALCUL COORDONNÉES
# =============================================================================

class TestCalculateCurrentCoords:
    """Tests pour _calculate_current_coords."""

    @pytest.fixture
    def session(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        """Crée une session pour les tests."""
        with patch('core.tracking.tracker.AbaqueManager') as mock_abaque_cls:
            with patch('core.tracking.tracker.AdaptiveTrackingManager'):
                mock_abaque_cls.return_value = mock_abaque_manager

                with patch.dict('sys.modules', {
                    'lgpio': MagicMock(),
                    'RPi': MagicMock(),
                    'RPi.GPIO': MagicMock()
                }):
                    from core.tracking.tracker import TrackingSession

                    session = TrackingSession(
                        moteur=mock_moteur,
                        calc=mock_calc,
                        logger=mock_tracking_logger,
                        abaque_file="data/Loi_coupole.xlsx",
                        encoder_config=mock_encoder_config,
                        motor_config=mock_motor_config
                    )

                    return session

    def test_calculate_coords_etoile(self, session, mock_calc):
        """Calcul pour une étoile (coordonnées fixes)."""
        session.is_planet = False
        session.ra_deg = 250.0
        session.dec_deg = 36.0
        mock_calc.calculer_coords_horizontales.return_value = (120.0, 45.0)

        now = datetime(2025, 6, 21, 22, 0, 0)
        az, alt = session._calculate_current_coords(now)

        assert az == 120.0
        assert alt == 45.0
        mock_calc.calculer_coords_horizontales.assert_called_once()


# =============================================================================
# TESTS STATISTIQUES ET ÉTAT
# =============================================================================

class TestTrackingSessionState:
    """Tests pour la gestion de l'état."""

    @pytest.fixture
    def session(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        """Crée une session pour les tests."""
        with patch('core.tracking.tracker.AbaqueManager') as mock_abaque_cls:
            with patch('core.tracking.tracker.AdaptiveTrackingManager'):
                mock_abaque_cls.return_value = mock_abaque_manager

                with patch.dict('sys.modules', {
                    'lgpio': MagicMock(),
                    'RPi': MagicMock(),
                    'RPi.GPIO': MagicMock()
                }):
                    from core.tracking.tracker import TrackingSession

                    return TrackingSession(
                        moteur=mock_moteur,
                        calc=mock_calc,
                        logger=mock_tracking_logger,
                        abaque_file="data/Loi_coupole.xlsx",
                        encoder_config=mock_encoder_config,
                        motor_config=mock_motor_config
                    )

    def test_correction_history_deque(self, session):
        """L'historique des corrections est une deque limitée."""
        assert isinstance(session.correction_history, deque)
        assert session.correction_history.maxlen == 10

    def test_position_cible_history_deque(self, session):
        """L'historique des positions cibles est une deque limitée."""
        assert isinstance(session._position_cible_history, deque)
        assert session._position_cible_history.maxlen == 5

    def test_drift_tracking_structure(self, session):
        """Structure du suivi de dérive."""
        assert 'start_time' in session.drift_tracking
        assert 'corrections_log' in session.drift_tracking
        assert isinstance(session.drift_tracking['corrections_log'], list)


# =============================================================================
# TESTS PROTECTION OSCILLATIONS
# =============================================================================

class TestOscillationProtection:
    """Tests pour la protection contre les oscillations."""

    @pytest.fixture
    def session(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        with patch('core.tracking.tracker.AbaqueManager') as mock_abaque_cls:
            with patch('core.tracking.tracker.AdaptiveTrackingManager'):
                mock_abaque_cls.return_value = mock_abaque_manager

                with patch.dict('sys.modules', {
                    'lgpio': MagicMock(),
                    'RPi': MagicMock(),
                    'RPi.GPIO': MagicMock()
                }):
                    from core.tracking.tracker import TrackingSession

                    return TrackingSession(
                        moteur=mock_moteur,
                        calc=mock_calc,
                        logger=mock_tracking_logger,
                        abaque_file="data/Loi_coupole.xlsx",
                        encoder_config=mock_encoder_config,
                        motor_config=mock_motor_config
                    )

    def test_oscillation_count_initial(self, session):
        """Compteur d'oscillations initialisé à 0."""
        assert session.oscillation_count == 0

    def test_consecutive_errors_initial(self, session):
        """Compteur d'erreurs consécutives initialisé à 0."""
        assert session.consecutive_errors == 0

    def test_max_consecutive_errors(self, session):
        """Limite max d'erreurs consécutives."""
        assert session.max_consecutive_errors == 5

    def test_failed_feedback_count_initial(self, session):
        """Compteur de feedback échoués initialisé à 0."""
        assert session.failed_feedback_count == 0


# =============================================================================
# TESTS INTÉGRATION ABAQUE
# =============================================================================

class TestAbaqueIntegration:
    """Tests pour l'intégration avec l'abaque."""

    @pytest.fixture
    def session(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        with patch('core.tracking.tracker.AbaqueManager') as mock_abaque_cls:
            with patch('core.tracking.tracker.AdaptiveTrackingManager'):
                mock_abaque_cls.return_value = mock_abaque_manager

                with patch.dict('sys.modules', {
                    'lgpio': MagicMock(),
                    'RPi': MagicMock(),
                    'RPi.GPIO': MagicMock()
                }):
                    from core.tracking.tracker import TrackingSession

                    return TrackingSession(
                        moteur=mock_moteur,
                        calc=mock_calc,
                        logger=mock_tracking_logger,
                        abaque_file="data/Loi_coupole.xlsx",
                        encoder_config=mock_encoder_config,
                        motor_config=mock_motor_config
                    )

    def test_abaque_manager_cree(self, session):
        """AbaqueManager est créé et chargé."""
        assert session.abaque_manager is not None
        assert session.abaque_manager.is_loaded is True

    def test_calculate_target_position_utilise_abaque(self, session):
        """_calculate_target_position utilise l'abaque."""
        session.abaque_manager.get_dome_position.return_value = (130.0, {})

        if hasattr(session, '_calculate_target_position'):
            result = session._calculate_target_position(120.0, 45.0)
            session.abaque_manager.get_dome_position.assert_called()


# =============================================================================
# TESTS INTÉGRATION ADAPTIVE
# =============================================================================

class TestAdaptiveIntegration:
    """Tests pour l'intégration avec le système adaptatif."""

    @pytest.fixture
    def session(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        with patch('core.tracking.tracker.AbaqueManager') as mock_abaque_cls:
            with patch('core.tracking.tracker.AdaptiveTrackingManager') as mock_adaptive_cls:
                mock_abaque_cls.return_value = mock_abaque_manager

                with patch.dict('sys.modules', {
                    'lgpio': MagicMock(),
                    'RPi': MagicMock(),
                    'RPi.GPIO': MagicMock()
                }):
                    from core.tracking.tracker import TrackingSession

                    session = TrackingSession(
                        moteur=mock_moteur,
                        calc=mock_calc,
                        logger=mock_tracking_logger,
                        abaque_file="data/Loi_coupole.xlsx",
                        encoder_config=mock_encoder_config,
                        motor_config=mock_motor_config
                    )

                    return session

    def test_adaptive_manager_cree(self, session):
        """AdaptiveTrackingManager est créé."""
        assert session.adaptive_manager is not None


# =============================================================================
# TESTS GET STATUS
# =============================================================================

class TestGetStatus:
    """Tests pour get_status."""

    @pytest.fixture
    def session(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        with patch('core.tracking.tracker.AbaqueManager') as mock_abaque_cls:
            with patch('core.tracking.tracker.AdaptiveTrackingManager'):
                mock_abaque_cls.return_value = mock_abaque_manager

                with patch.dict('sys.modules', {
                    'lgpio': MagicMock(),
                    'RPi': MagicMock(),
                    'RPi.GPIO': MagicMock()
                }):
                    from core.tracking.tracker import TrackingSession

                    return TrackingSession(
                        moteur=mock_moteur,
                        calc=mock_calc,
                        logger=mock_tracking_logger,
                        abaque_file="data/Loi_coupole.xlsx",
                        encoder_config=mock_encoder_config,
                        motor_config=mock_motor_config
                    )

    def test_get_status_quand_non_running(self, session):
        """get_status quand la session n'est pas active."""
        session.running = False

        if hasattr(session, 'get_status'):
            status = session.get_status()
            assert isinstance(status, dict)


# =============================================================================
# TESTS PARAMÈTRES CORRECTIONS
# =============================================================================

class TestCorrectionParameters:
    """Tests pour les paramètres de correction."""

    @pytest.fixture
    def session(
        self, mock_moteur, mock_calc, mock_tracking_logger,
        mock_encoder_config, mock_motor_config, mock_abaque_manager
    ):
        with patch('core.tracking.tracker.AbaqueManager') as mock_abaque_cls:
            with patch('core.tracking.tracker.AdaptiveTrackingManager'):
                mock_abaque_cls.return_value = mock_abaque_manager

                with patch.dict('sys.modules', {
                    'lgpio': MagicMock(),
                    'RPi': MagicMock(),
                    'RPi.GPIO': MagicMock()
                }):
                    from core.tracking.tracker import TrackingSession

                    return TrackingSession(
                        moteur=mock_moteur,
                        calc=mock_calc,
                        logger=mock_tracking_logger,
                        seuil=0.3,
                        intervalle=30,
                        abaque_file="data/Loi_coupole.xlsx",
                        encoder_config=mock_encoder_config,
                        motor_config=mock_motor_config
                    )

    def test_seuil_configure(self, session):
        """Le seuil est correctement configuré."""
        assert session.seuil == 0.3

    def test_intervalle_configure(self, session):
        """L'intervalle est correctement configuré."""
        assert session.intervalle == 30

    def test_steps_correction_factor(self, session):
        """Le facteur de correction des pas est configuré."""
        assert session.steps_correction_factor == 1.08849
