"""
Tests pour le système de simulation réaliste.

Ce module teste le MovementSimulator qui fournit une simulation
temporelle réaliste des mouvements moteur.
"""

import pytest
import time
import threading

from core.hardware.moteur_simule import (
    MovementSimulator,
    MovementState,
    get_movement_simulator,
    set_simulated_position,
    get_simulated_position,
    MoteurSimule,
    SimulatedDaemonReader,
    SWITCH_CALIB_ANGLE
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def fresh_simulator():
    """Crée un simulateur frais pour chaque test (reset singleton)."""
    # Reset le singleton
    MovementSimulator._instance = None
    MovementSimulator._lock = threading.Lock()

    # Créer une nouvelle instance
    simulator = MovementSimulator()
    simulator.set_position(0.0)

    yield simulator

    # Cleanup
    MovementSimulator._instance = None


@pytest.fixture
def moteur_simule():
    """Crée un moteur simulé pour les tests."""
    # Reset le simulateur
    MovementSimulator._instance = None
    MovementSimulator._lock = threading.Lock()

    moteur = MoteurSimule()
    yield moteur

    # Cleanup
    MovementSimulator._instance = None


# =============================================================================
# Tests MovementSimulator - Calculs de vitesse
# =============================================================================

class TestMovementSimulatorSpeed:
    """Tests pour les calculs de vitesse."""

    def test_calculate_speed_from_delay_continuous(self, fresh_simulator):
        """Vitesse CONTINUOUS (motor_delay=0.00015s)."""
        speed = fresh_simulator.calculate_speed_from_delay(0.00015)
        # Environ 1.2°/s avec 1941866 steps/rev
        assert speed > 1.0
        assert speed < 2.0

    def test_calculate_speed_from_delay_normal(self, fresh_simulator):
        """Vitesse NORMAL (motor_delay=0.002s)."""
        speed = fresh_simulator.calculate_speed_from_delay(0.002)
        # Plus lent que CONTINUOUS
        assert speed < 0.15

    def test_calculate_speed_from_delay_zero(self, fresh_simulator):
        """Délai zéro utilise la vitesse par défaut."""
        speed = fresh_simulator.calculate_speed_from_delay(0)
        # Devrait retourner ~0.683°/s (41°/min)
        assert speed == pytest.approx(41.0 / 60.0, rel=0.01)


# =============================================================================
# Tests MovementSimulator - Mouvements
# =============================================================================

class TestMovementSimulatorMovements:
    """Tests pour les mouvements simulés."""

    def test_start_movement_sets_state(self, fresh_simulator):
        """Démarrer un mouvement crée l'état."""
        fresh_simulator.start_movement(delta=90.0, speed=0.00015)

        info = fresh_simulator.get_movement_info()
        assert info is not None
        assert info['delta'] == 90.0
        assert info['start_position'] == 0.0
        assert info['target_position'] == 90.0

    def test_is_moving_during_movement(self, fresh_simulator):
        """is_moving() retourne True pendant un mouvement."""
        fresh_simulator.start_movement(delta=90.0, speed=0.00015)

        # Doit être en mouvement immédiatement
        assert fresh_simulator.is_moving() is True

    def test_position_interpolated_during_movement(self, fresh_simulator):
        """La position est interpolée pendant le mouvement."""
        fresh_simulator.start_movement(delta=10.0, speed=0.00015)

        # Attendre un peu
        time.sleep(0.1)

        pos = fresh_simulator.get_current_position()
        # La position doit avoir avancé mais pas atteint la cible
        assert pos > 0.0
        # Doit être encore loin de la cible (10° prend ~8s à cette vitesse)
        assert pos < 10.0

    def test_stop_movement(self, fresh_simulator):
        """Arrêter un mouvement fige la position."""
        fresh_simulator.start_movement(delta=90.0, speed=0.00015)
        time.sleep(0.1)

        stopped_pos = fresh_simulator.stop_movement()

        assert fresh_simulator.is_moving() is False
        assert fresh_simulator.get_current_position() == stopped_pos

    def test_set_position_direct(self, fresh_simulator):
        """set_position() définit la position directement."""
        fresh_simulator.set_position(180.0)

        assert fresh_simulator.get_current_position() == 180.0
        assert fresh_simulator.is_moving() is False

    def test_set_position_normalizes(self, fresh_simulator):
        """set_position() normalise les angles > 360."""
        fresh_simulator.set_position(450.0)

        assert fresh_simulator.get_current_position() == 90.0


# =============================================================================
# Tests MovementSimulator - Mouvements absolus
# =============================================================================

class TestMovementSimulatorAbsolute:
    """Tests pour les mouvements absolus."""

    def test_absolute_movement_positive_delta(self, fresh_simulator):
        """Mouvement absolu avec delta positif."""
        fresh_simulator.set_position(0.0)
        delta = fresh_simulator.start_absolute_movement(target=90.0, speed=0.00015)

        assert delta == 90.0
        info = fresh_simulator.get_movement_info()
        assert info['target_position'] == 90.0

    def test_absolute_movement_negative_delta(self, fresh_simulator):
        """Mouvement absolu avec delta négatif (chemin court)."""
        fresh_simulator.set_position(10.0)
        delta = fresh_simulator.start_absolute_movement(target=350.0, speed=0.00015)

        # Chemin le plus court: 10° → 350° = -20°
        assert delta == -20.0

    def test_absolute_movement_crosses_zero(self, fresh_simulator):
        """Mouvement absolu traversant 0°."""
        fresh_simulator.set_position(350.0)
        delta = fresh_simulator.start_absolute_movement(target=10.0, speed=0.00015)

        # Chemin le plus court: 350° → 10° = +20°
        assert delta == 20.0


# =============================================================================
# Tests MoteurSimule avec timing réaliste
# =============================================================================

class TestMoteurSimuleRealistic:
    """Tests pour le moteur simulé avec timing réaliste."""

    def test_rotation_takes_time(self, moteur_simule):
        """Une rotation prend du temps réel."""
        start = time.time()

        # Rotation de 5° à vitesse CONTINUOUS (~1.2°/s)
        moteur_simule.rotation(5.0, vitesse=0.00015)

        elapsed = time.time() - start

        # Doit prendre quelques secondes (5° / ~1.2°/s ≈ 4s)
        assert elapsed > 3.0
        assert elapsed < 6.0

    def test_rotation_can_be_stopped(self, moteur_simule):
        """Une rotation peut être arrêtée."""
        def stop_after_delay():
            time.sleep(0.5)
            moteur_simule.request_stop()

        # Lancer l'arrêt en parallèle
        stopper = threading.Thread(target=stop_after_delay)
        stopper.start()

        start = time.time()
        moteur_simule.rotation(90.0, vitesse=0.00015)  # ~75s normalement
        elapsed = time.time() - start

        stopper.join()

        # Doit être arrêté en ~0.5s
        assert elapsed < 2.0

    def test_get_daemon_angle_during_movement(self, moteur_simule):
        """get_daemon_angle() retourne la position interpolée."""
        moteur_simule._simulator.start_movement(delta=10.0, speed=0.00015)

        time.sleep(0.1)

        angle = MoteurSimule.get_daemon_angle()

        # Doit être entre 0 et 10
        assert angle > 0.0
        assert angle < 10.0

    def test_rotation_avec_feedback_takes_time(self, moteur_simule):
        """rotation_avec_feedback() prend du temps réel."""
        # S'assurer de partir de 0
        moteur_simule._simulator.set_position(0.0)

        start = time.time()

        result = moteur_simule.rotation_avec_feedback(
            angle_cible=5.0,
            vitesse=0.00015
        )

        # Le temps réel doit être > 0 (pas instantané)
        # 5° à ~1.2°/s ≈ 4s
        assert result['temps_total'] > 3.0
        assert result['mode'] == 'simulation'


# =============================================================================
# Tests SimulatedDaemonReader
# =============================================================================

class TestSimulatedDaemonReader:
    """Tests pour le lecteur de daemon simulé."""

    def test_is_available(self):
        """Le daemon simulé est toujours disponible."""
        MovementSimulator._instance = None
        reader = SimulatedDaemonReader()

        assert reader.is_available() is True

    def test_read_angle_interpolated(self):
        """read_angle() retourne la position interpolée."""
        MovementSimulator._instance = None
        simulator = get_movement_simulator()
        reader = SimulatedDaemonReader()

        # Démarrer un mouvement
        simulator.start_movement(delta=10.0, speed=0.00015)
        time.sleep(0.1)

        angle1 = reader.read_angle()
        time.sleep(0.1)
        angle2 = reader.read_angle()

        # Les angles doivent progresser
        assert angle2 > angle1

    def test_read_raw_structure(self):
        """read_raw() retourne la structure correcte."""
        MovementSimulator._instance = None
        reader = SimulatedDaemonReader()

        raw = reader.read_raw()

        assert 'angle' in raw
        assert 'calibrated' in raw
        assert isinstance(raw['calibrated'], bool)  # Réaliste: False jusqu'au passage sur 45°
        assert 'raw' in raw  # Valeur brute encodeur (0-1023)
        assert 'simulation' in raw['status']


# =============================================================================
# Tests helper functions
# =============================================================================

class TestHelperFunctions:
    """Tests pour les fonctions helper."""

    def test_set_simulated_position(self):
        """set_simulated_position() définit la position."""
        MovementSimulator._instance = None

        set_simulated_position(123.0)

        assert get_simulated_position() == 123.0

    def test_get_simulated_position_during_movement(self):
        """get_simulated_position() retourne la position interpolée."""
        MovementSimulator._instance = None
        simulator = get_movement_simulator()
        simulator.set_position(0.0)  # Reset position

        simulator.start_movement(delta=10.0, speed=0.00015)
        time.sleep(0.1)

        pos = get_simulated_position()

        # Doit être entre 0 et 10
        assert pos > 0.0
        assert pos < 10.0


# =============================================================================
# Tests Switch de Calibration (SS-5GL à 45°)
# =============================================================================

class TestCalibrationSwitch:
    """Tests pour la simulation du switch de calibration."""

    def test_initial_calibrated_false(self, fresh_simulator):
        """Initialement, le système n'est pas calibré."""
        assert fresh_simulator.is_calibrated is False

    def test_crossing_45_triggers_calibration(self, fresh_simulator):
        """Traverser 45° active la calibration."""
        fresh_simulator.set_position(40.0)
        fresh_simulator.reset_calibration()

        # Traverser 45°
        fresh_simulator.set_position(50.0)

        assert fresh_simulator.is_calibrated is True

    def test_crossing_45_backward_triggers_calibration(self, fresh_simulator):
        """Traverser 45° en sens inverse active aussi la calibration."""
        fresh_simulator.set_position(50.0)
        fresh_simulator.reset_calibration()

        # Traverser 45° en sens inverse
        fresh_simulator.set_position(40.0)

        assert fresh_simulator.is_calibrated is True

    def test_no_crossing_no_calibration(self, fresh_simulator):
        """Rester du même côté de 45° ne déclenche pas la calibration."""
        fresh_simulator.set_position(50.0)
        fresh_simulator.reset_calibration()

        # Mouvement sans traverser 45°
        fresh_simulator.set_position(60.0)

        assert fresh_simulator.is_calibrated is False

    def test_switch_callback_called(self, fresh_simulator):
        """Le callback est appelé quand le switch est activé."""
        callback_called = []

        def on_switch(angle):
            callback_called.append(angle)

        fresh_simulator.set_switch_callback(on_switch)
        fresh_simulator.set_position(40.0)
        fresh_simulator.reset_calibration()

        # Traverser 45°
        fresh_simulator.set_position(50.0)

        assert len(callback_called) == 1
        assert callback_called[0] == SWITCH_CALIB_ANGLE

    def test_calibration_only_once(self, fresh_simulator):
        """La calibration ne se déclenche qu'une fois."""
        callback_count = [0]

        def on_switch(angle):
            callback_count[0] += 1

        fresh_simulator.set_switch_callback(on_switch)
        fresh_simulator.set_position(40.0)
        fresh_simulator.reset_calibration()

        # Premier passage
        fresh_simulator.set_position(50.0)
        # Retour
        fresh_simulator.set_position(40.0)
        # Second passage
        fresh_simulator.set_position(50.0)

        # Le callback n'est appelé qu'une fois
        assert callback_count[0] == 1

    def test_reset_allows_recalibration(self, fresh_simulator):
        """reset_calibration() permet une nouvelle calibration."""
        fresh_simulator.set_position(40.0)
        fresh_simulator.set_position(50.0)  # Première calibration

        fresh_simulator.reset_calibration()
        fresh_simulator.set_position(40.0)
        fresh_simulator.set_position(50.0)  # Deuxième calibration

        assert fresh_simulator.is_calibrated is True


class TestRawEncoderValue:
    """Tests pour la simulation des valeurs brutes de l'encodeur."""

    def test_raw_value_in_range(self, fresh_simulator):
        """La valeur raw est dans l'intervalle 0-1023."""
        fresh_simulator.set_position(0.0)
        raw = fresh_simulator.get_raw_encoder_value()

        assert 0 <= raw < 1024

    def test_raw_value_changes_with_position(self, fresh_simulator):
        """La valeur raw change avec la position."""
        fresh_simulator.set_position(0.0)
        raw1 = fresh_simulator.get_raw_encoder_value()

        fresh_simulator.set_position(90.0)
        raw2 = fresh_simulator.get_raw_encoder_value()

        assert raw1 != raw2


class TestSimulatedDaemonReaderCalibration:
    """Tests pour SimulatedDaemonReader avec calibration."""

    def test_read_raw_includes_calibrated(self):
        """read_raw() inclut le flag calibrated."""
        MovementSimulator._instance = None
        simulator = get_movement_simulator()
        simulator.reset_calibration()
        reader = SimulatedDaemonReader()

        raw = reader.read_raw()

        assert 'calibrated' in raw
        assert raw['calibrated'] is False

    def test_calibrated_after_crossing_45(self):
        """Le flag calibrated devient True après passage sur 45°."""
        MovementSimulator._instance = None
        simulator = get_movement_simulator()
        simulator.set_position(40.0)
        simulator.reset_calibration()

        reader = SimulatedDaemonReader()

        # Avant le passage
        assert reader.read_raw()['calibrated'] is False

        # Traverser 45°
        simulator.set_position(50.0)

        # Après le passage
        assert reader.read_raw()['calibrated'] is True

    def test_read_raw_includes_realistic_raw(self):
        """read_raw() inclut une valeur raw réaliste."""
        MovementSimulator._instance = None
        simulator = get_movement_simulator()
        simulator.set_position(180.0)

        reader = SimulatedDaemonReader()
        raw = reader.read_raw()

        assert 'raw' in raw
        assert 0 <= raw['raw'] < 1024

    def test_is_calibrated_method(self):
        """La méthode is_calibrated() fonctionne."""
        MovementSimulator._instance = None
        simulator = get_movement_simulator()
        simulator.set_position(40.0)
        simulator.reset_calibration()

        reader = SimulatedDaemonReader()

        assert reader.is_calibrated() is False

        simulator.set_position(50.0)

        assert reader.is_calibrated() is True
