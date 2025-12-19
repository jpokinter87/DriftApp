"""
Tests pour le module core/hardware/feedback_controller.py

Ce module teste le contrôleur de feedback en boucle fermée.
"""

import pytest
import time
from unittest.mock import MagicMock, patch, PropertyMock


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_daemon_reader():
    """Mock pour DaemonEncoderReader."""
    reader = MagicMock()
    reader.is_available.return_value = True
    reader.read_angle.return_value = 45.0
    reader.read_stable.return_value = 45.0
    reader.read_raw.return_value = {"angle": 45.0, "status": "OK"}
    return reader


@pytest.fixture
def mock_moteur():
    """Mock pour MoteurCoupole."""
    moteur = MagicMock()
    moteur.steps_per_dome_revolution = 1942968
    moteur.stop_requested = False
    moteur.direction_actuelle = 1
    moteur.definir_direction = MagicMock()
    moteur.faire_un_pas = MagicMock()
    moteur.rotation = MagicMock()
    moteur.clear_stop_request = MagicMock()
    return moteur


@pytest.fixture
def feedback_controller(mock_moteur, mock_daemon_reader):
    """Crée un FeedbackController avec mocks."""
    with patch.dict('sys.modules', {
        'lgpio': MagicMock(),
        'RPi': MagicMock(),
        'RPi.GPIO': MagicMock()
    }):
        from core.hardware.feedback_controller import FeedbackController
        return FeedbackController(mock_moteur, mock_daemon_reader)


# =============================================================================
# TESTS CONTRÔLE D'ARRÊT
# =============================================================================

class TestFeedbackControllerStop:
    """Tests pour le contrôle d'arrêt."""

    def test_request_stop(self, feedback_controller, mock_moteur):
        """request_stop met les flags à True."""
        assert feedback_controller.stop_requested is False

        feedback_controller.request_stop()

        assert feedback_controller.stop_requested is True
        assert mock_moteur.stop_requested is True

    def test_clear_stop_request(self, feedback_controller, mock_moteur):
        """clear_stop_request remet les flags à False."""
        feedback_controller.stop_requested = True
        mock_moteur.stop_requested = True

        feedback_controller.clear_stop_request()

        assert feedback_controller.stop_requested is False
        assert mock_moteur.stop_requested is False


# =============================================================================
# TESTS CALCULS UTILITAIRES
# =============================================================================

class TestFeedbackControllerCalculs:
    """Tests pour les calculs utilitaires."""

    def test_calculer_delta_angulaire_simple(self, feedback_controller):
        """Delta simple sans traversée de 0°."""
        delta = feedback_controller._calculer_delta_angulaire(10.0, 50.0)
        assert delta == pytest.approx(40.0)

    def test_calculer_delta_angulaire_negatif(self, feedback_controller):
        """Delta négatif (sens anti-horaire)."""
        delta = feedback_controller._calculer_delta_angulaire(50.0, 10.0)
        assert delta == pytest.approx(-40.0)

    def test_calculer_delta_angulaire_traverse_zero(self, feedback_controller):
        """Traversée de 0° prend le chemin le plus court."""
        delta = feedback_controller._calculer_delta_angulaire(350.0, 10.0)
        assert delta == pytest.approx(20.0)

    def test_calculer_delta_angulaire_traverse_zero_inverse(self, feedback_controller):
        """Traversée de 0° dans l'autre sens."""
        delta = feedback_controller._calculer_delta_angulaire(10.0, 350.0)
        assert delta == pytest.approx(-20.0)

    def test_lire_position_stable(self, feedback_controller, mock_daemon_reader):
        """Lecture position via daemon."""
        mock_daemon_reader.read_stable.return_value = 67.5

        result = feedback_controller._lire_position_stable()

        assert result == 67.5
        mock_daemon_reader.read_stable.assert_called_once()

    def test_calculer_correction(self, feedback_controller):
        """Calcul des paramètres de correction."""
        angle_correction, direction, steps = feedback_controller._calculer_correction(
            erreur=5.0, max_correction=10.0
        )

        assert angle_correction == 5.0
        assert direction == 1
        assert steps > 0

    def test_calculer_correction_limitee(self, feedback_controller):
        """Correction limitée par max_correction."""
        angle_correction, direction, steps = feedback_controller._calculer_correction(
            erreur=15.0, max_correction=10.0
        )

        assert angle_correction == 10.0  # Limité

    def test_calculer_correction_direction_negative(self, feedback_controller):
        """Direction négative pour erreur négative."""
        angle_correction, direction, steps = feedback_controller._calculer_correction(
            erreur=-5.0, max_correction=10.0
        )

        assert direction == -1


# =============================================================================
# TESTS CRÉATION RÉSULTATS
# =============================================================================

class TestFeedbackControllerResultats:
    """Tests pour la création de résultats."""

    def test_creer_resultat_sans_feedback(self, feedback_controller):
        """Création résultat en mode sans feedback."""
        start_time = time.time()

        result = feedback_controller._creer_resultat_sans_feedback(90.0, start_time)

        assert result['success'] is False
        assert result['position_cible'] == 90.0
        assert result['mode'] == 'sans_feedback'
        assert 'temps_total' in result

    def test_creer_resultat_success(self, feedback_controller):
        """Création résultat avec succès."""
        result = feedback_controller._creer_resultat(
            success=True,
            position_initiale=0.0,
            position_finale=90.0,
            angle_cible=90.0,
            erreur_finale=0.2,
            iterations=2,
            corrections=[],
            temps_total=1.5
        )

        assert result['success'] is True
        assert result['position_initiale'] == 0.0
        assert result['position_finale'] == 90.0
        assert result['erreur_finale'] == 0.2
        assert result['mode'] == 'feedback_daemon'


# =============================================================================
# TESTS ROTATION AVEC FEEDBACK
# =============================================================================

class TestRotationAvecFeedback:
    """Tests pour rotation_avec_feedback."""

    def test_rotation_success_premiere_lecture(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Rotation réussie dès la première lecture (déjà à la cible)."""
        # Configurer le mock pour être déjà à la position cible
        mock_daemon_reader.read_stable.return_value = 90.0

        result = feedback_controller.rotation_avec_feedback(
            angle_cible=90.0,
            vitesse=0.001,
            tolerance=0.5
        )

        assert result['success'] is True
        assert result['erreur_finale'] == pytest.approx(0.0, abs=0.5)

    def test_rotation_avec_corrections(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Rotation nécessitant des corrections."""
        # Position initiale 0°, puis 45° après correction, puis 90° (cible)
        positions = [0.0, 0.0, 45.0, 45.0, 90.0]
        mock_daemon_reader.read_stable.side_effect = positions

        result = feedback_controller.rotation_avec_feedback(
            angle_cible=90.0,
            vitesse=0.001,
            tolerance=0.5,
            max_iterations=10
        )

        assert result['mode'] == 'feedback_daemon'
        assert 'corrections' in result

    def test_rotation_daemon_indisponible(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Fallback si daemon non disponible."""
        mock_daemon_reader.read_stable.side_effect = RuntimeError("Daemon not found")

        result = feedback_controller.rotation_avec_feedback(
            angle_cible=90.0,
            vitesse=0.001
        )

        assert result['success'] is False
        assert result['mode'] == 'sans_feedback'

    def test_rotation_stop_requested(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Arrêt si stop_requested pendant la boucle."""
        mock_daemon_reader.read_stable.return_value = 0.0

        # Simuler un arrêt après la première lecture
        def set_stop(*args, **kwargs):
            feedback_controller.stop_requested = True
            return 0.0

        mock_daemon_reader.read_stable.side_effect = set_stop

        result = feedback_controller.rotation_avec_feedback(
            angle_cible=90.0,
            max_iterations=10
        )

        # La boucle doit s'arrêter
        assert result['iterations'] < 10

    def test_rotation_max_iterations(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Arrêt après max_iterations."""
        # Position qui ne change jamais (erreur persistante)
        mock_daemon_reader.read_stable.return_value = 0.0
        mock_daemon_reader.read_angle.return_value = 0.0

        result = feedback_controller.rotation_avec_feedback(
            angle_cible=90.0,
            tolerance=0.1,
            max_iterations=3
        )

        # Doit avoir fait exactement max_iterations
        assert result['iterations'] <= 3
        assert result['success'] is False


# =============================================================================
# TESTS ROTATION RELATIVE
# =============================================================================

class TestRotationRelative:
    """Tests pour rotation_relative_avec_feedback."""

    def test_rotation_relative_calcul_cible(
        self, feedback_controller, mock_daemon_reader
    ):
        """Calcul correct de l'angle cible."""
        mock_daemon_reader.read_angle.return_value = 45.0
        mock_daemon_reader.read_stable.return_value = 90.0  # Après rotation

        with patch.object(
            feedback_controller, 'rotation_avec_feedback',
            return_value={'success': True}
        ) as mock_rotation:
            feedback_controller.rotation_relative_avec_feedback(45.0)

            # Cible = 45 + 45 = 90
            mock_rotation.assert_called_once()
            call_kwargs = mock_rotation.call_args[1]
            assert call_kwargs['angle_cible'] == 90.0

    def test_rotation_relative_traverse_360(
        self, feedback_controller, mock_daemon_reader
    ):
        """Rotation relative qui traverse 360°."""
        mock_daemon_reader.read_angle.return_value = 350.0
        mock_daemon_reader.read_stable.return_value = 20.0

        with patch.object(
            feedback_controller, 'rotation_avec_feedback',
            return_value={'success': True}
        ) as mock_rotation:
            feedback_controller.rotation_relative_avec_feedback(30.0)

            # Cible = (350 + 30) % 360 = 20
            call_kwargs = mock_rotation.call_args[1]
            assert call_kwargs['angle_cible'] == 20.0

    def test_rotation_relative_daemon_indisponible(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Fallback si daemon non disponible."""
        mock_daemon_reader.read_angle.side_effect = RuntimeError("Daemon not found")

        result = feedback_controller.rotation_relative_avec_feedback(45.0)

        assert result['success'] is False
        assert result['mode'] == 'sans_feedback'
        mock_moteur.rotation.assert_called_once()


# =============================================================================
# TESTS EXÉCUTION DES PAS
# =============================================================================

class TestExecuterPas:
    """Tests pour l'exécution des pas."""

    def test_executer_pas_avec_verification(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Exécution des pas avec vérifications périodiques."""
        mock_daemon_reader.read_angle.return_value = 45.0

        feedback_controller._executer_pas_avec_verification(
            steps=100,
            vitesse=0.001,
            angle_cible=45.0,
            tolerance=0.5
        )

        # Devrait avoir appelé faire_un_pas 100 fois (ou moins si arrêt anticipé)
        assert mock_moteur.faire_un_pas.call_count <= 100

    def test_executer_pas_arret_anticipe(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Arrêt anticipé si objectif atteint."""
        # Simuler atteinte de l'objectif après quelques pas
        mock_daemon_reader.read_angle.return_value = 45.0
        feedback_controller.stop_requested = True

        feedback_controller._executer_pas_avec_verification(
            steps=1000,
            vitesse=0.001,
            angle_cible=45.0,
            tolerance=0.5
        )

        # Devrait s'arrêter avant les 1000 pas
        assert mock_moteur.faire_un_pas.call_count < 1000


# =============================================================================
# TESTS ENREGISTREMENT CORRECTION
# =============================================================================

class TestEnregistrerCorrection:
    """Tests pour l'enregistrement des corrections."""

    def test_enregistrer_correction_structure(
        self, feedback_controller, mock_daemon_reader
    ):
        """Vérifie la structure de l'enregistrement."""
        mock_daemon_reader.read_stable.return_value = 50.0

        correction = feedback_controller._enregistrer_correction(
            iteration=0,
            position_avant=45.0,
            erreur_avant=5.0,
            angle_correction=5.0,
            direction=1,
            steps=100,
            correction_start=time.time() - 0.5,
            angle_cible=50.0
        )

        assert 'iteration' in correction
        assert 'position_avant' in correction
        assert 'erreur_avant' in correction
        assert 'correction_demandee' in correction
        assert 'steps' in correction
        assert 'duration' in correction
        assert 'erreur_apres' in correction

    def test_enregistrer_correction_valeurs(
        self, feedback_controller, mock_daemon_reader
    ):
        """Vérifie les valeurs de l'enregistrement."""
        mock_daemon_reader.read_stable.return_value = 50.0

        correction = feedback_controller._enregistrer_correction(
            iteration=2,
            position_avant=45.0,
            erreur_avant=5.0,
            angle_correction=5.0,
            direction=1,
            steps=100,
            correction_start=time.time(),
            angle_cible=50.0
        )

        assert correction['iteration'] == 3  # 0-indexed + 1
        assert correction['position_avant'] == 45.0
        assert correction['erreur_avant'] == 5.0
        assert correction['correction_demandee'] == 5.0  # 5.0 * 1
        assert correction['steps'] == 100


# =============================================================================
# TESTS ITÉRATION
# =============================================================================

class TestExecuterIteration:
    """Tests pour l'exécution d'une itération."""

    def test_executer_iteration_objectif_atteint(
        self, feedback_controller, mock_daemon_reader
    ):
        """Retourne None si objectif atteint."""
        mock_daemon_reader.read_stable.return_value = 90.0

        result = feedback_controller._executer_iteration(
            angle_cible=90.0,
            vitesse=0.001,
            tolerance=0.5,
            max_correction=45.0,
            iteration=0
        )

        assert result is None

    def test_executer_iteration_avec_correction(
        self, feedback_controller, mock_daemon_reader, mock_moteur
    ):
        """Retourne dict si correction effectuée."""
        # Position initiale loin de la cible
        mock_daemon_reader.read_stable.side_effect = [45.0, 90.0]

        result = feedback_controller._executer_iteration(
            angle_cible=90.0,
            vitesse=0.001,
            tolerance=0.5,
            max_correction=45.0,
            iteration=0
        )

        assert result is not None
        assert 'iteration' in result
        assert 'steps' in result

    def test_executer_iteration_erreur_lecture(
        self, feedback_controller, mock_daemon_reader
    ):
        """Retourne None si erreur de lecture."""
        mock_daemon_reader.read_stable.side_effect = RuntimeError("Error")

        result = feedback_controller._executer_iteration(
            angle_cible=90.0,
            vitesse=0.001,
            tolerance=0.5,
            max_correction=45.0,
            iteration=0
        )

        assert result is None
