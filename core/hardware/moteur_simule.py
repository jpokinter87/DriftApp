"""
Moteur simulé pour tests sans matériel.

Cette classe simule l'interface du MoteurCoupole pour permettre
le développement et les tests sans accès au matériel réel.

VERSION 4.0 : Intègre les méthodes de feedback simulées.
VERSION 4.3 : Ajout get_feedback_controller, get_daemon_angle, rotation_absolue
              pour compatibilité avec MoteurCoupole refactorisé.
VERSION 4.4 : Simulation réaliste du déplacement (faire_un_pas, get_daemon_angle)
VERSION 4.5 : MovementSimulator avec timing réaliste (interpolation temporelle)
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional


# =============================================================================
# MOVEMENT SIMULATOR - Simulation temporelle réaliste
# =============================================================================

@dataclass
class MovementState:
    """État d'un mouvement en cours."""
    start_time: float
    start_position: float
    target_position: float
    delta: float  # Signé, direction du mouvement
    speed_deg_per_sec: float
    duration_sec: float


class MovementSimulator:
    """
    Simule le mouvement du moteur avec timing réaliste.

    Au lieu de mettre à jour la position instantanément, cette classe
    interpole la position en fonction du temps écoulé, simulant ainsi
    le comportement réel du moteur.

    Vitesses typiques (depuis config.json):
    - CONTINUOUS: ~41°/min (0.683°/s) - motor_delay 0.00015s
    - CRITICAL: ~9°/min (0.15°/s) - motor_delay 0.001s
    - NORMAL: ~5°/min (0.083°/s) - motor_delay 0.002s
    """

    # Singleton pour partager l'état entre instances
    _instance: Optional['MovementSimulator'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern pour état partagé."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = logging.getLogger("MovementSimulator")
        self._current_movement: Optional[MovementState] = None
        self._position: float = 0.0  # Position au repos
        self._movement_lock = threading.Lock()
        self._initialized = True

        # Steps per revolution (sera mis à jour par MoteurSimule)
        self._steps_per_revolution = 1941866

        self.logger.debug("MovementSimulator initialisé")

    def set_steps_per_revolution(self, steps: int):
        """Configure le nombre de pas par révolution."""
        self._steps_per_revolution = steps

    def calculate_speed_from_delay(self, motor_delay: float) -> float:
        """
        Calcule la vitesse en °/s à partir du délai moteur.

        Args:
            motor_delay: Délai entre chaque pas en secondes

        Returns:
            Vitesse en degrés par seconde
        """
        if motor_delay <= 0:
            # Vitesse par défaut CONTINUOUS: ~41°/min
            return 41.0 / 60.0

        # Degrés par pas
        deg_per_step = 360.0 / self._steps_per_revolution

        # Pas par seconde
        steps_per_sec = 1.0 / motor_delay

        # Degrés par seconde
        return deg_per_step * steps_per_sec

    def start_movement(self, delta: float, speed: float = 0.00015) -> None:
        """
        Démarre un mouvement simulé.

        Args:
            delta: Angle de rotation en degrés (signé)
            speed: Délai moteur en secondes (motor_delay)
        """
        with self._movement_lock:
            # Calculer la vitesse en °/s
            speed_deg_per_sec = self.calculate_speed_from_delay(speed)

            # Durée du mouvement
            duration = abs(delta) / speed_deg_per_sec if speed_deg_per_sec > 0 else 0

            # Position de départ = position actuelle interpolée
            start_pos = self._get_current_position_unsafe()
            target_pos = (start_pos + delta) % 360

            self._current_movement = MovementState(
                start_time=time.time(),
                start_position=start_pos,
                target_position=target_pos,
                delta=delta,
                speed_deg_per_sec=speed_deg_per_sec,
                duration_sec=duration
            )

            self.logger.debug(
                f"Mouvement démarré: {start_pos:.1f}° → {target_pos:.1f}° "
                f"(Δ={delta:+.1f}°, vitesse={speed_deg_per_sec:.2f}°/s, "
                f"durée={duration:.1f}s)"
            )

    def start_absolute_movement(self, target: float, speed: float = 0.00015) -> float:
        """
        Démarre un mouvement vers une position absolue.

        Args:
            target: Position cible en degrés
            speed: Délai moteur en secondes

        Returns:
            Delta calculé (pour info)
        """
        current = self.get_current_position()

        # Calcul du delta (chemin le plus court)
        delta = target - current
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360

        self.start_movement(delta, speed)
        return delta

    def stop_movement(self) -> float:
        """
        Arrête le mouvement en cours et retourne la position finale.

        Returns:
            Position actuelle au moment de l'arrêt
        """
        with self._movement_lock:
            pos = self._get_current_position_unsafe()
            self._position = pos
            self._current_movement = None
            return pos

    def _get_current_position_unsafe(self) -> float:
        """
        Retourne la position actuelle (sans lock).
        À utiliser uniquement quand le lock est déjà acquis.
        """
        if self._current_movement is None:
            return self._position

        mv = self._current_movement
        elapsed = time.time() - mv.start_time

        if elapsed >= mv.duration_sec:
            # Mouvement terminé
            self._position = mv.target_position
            self._current_movement = None
            return self._position

        # Interpolation linéaire
        progress = elapsed / mv.duration_sec if mv.duration_sec > 0 else 1.0
        distance_traveled = abs(mv.delta) * progress
        direction = 1 if mv.delta >= 0 else -1

        current = (mv.start_position + direction * distance_traveled) % 360
        return current

    def get_current_position(self) -> float:
        """
        Retourne la position actuelle interpolée.

        Si un mouvement est en cours, calcule la position
        en fonction du temps écoulé.
        """
        with self._movement_lock:
            return self._get_current_position_unsafe()

    def is_moving(self) -> bool:
        """Retourne True si un mouvement est en cours."""
        with self._movement_lock:
            if self._current_movement is None:
                return False

            elapsed = time.time() - self._current_movement.start_time
            return elapsed < self._current_movement.duration_sec

    def get_movement_info(self) -> Optional[dict]:
        """
        Retourne les informations sur le mouvement en cours.

        Returns:
            Dict avec progress, remaining_seconds, etc. ou None si pas de mouvement
        """
        with self._movement_lock:
            if self._current_movement is None:
                return None

            mv = self._current_movement
            elapsed = time.time() - mv.start_time

            if elapsed >= mv.duration_sec:
                return None

            progress = (elapsed / mv.duration_sec * 100) if mv.duration_sec > 0 else 100
            remaining = mv.duration_sec - elapsed

            return {
                'start_position': mv.start_position,
                'target_position': mv.target_position,
                'current_position': self._get_current_position_unsafe(),
                'delta': mv.delta,
                'progress': progress,
                'remaining_seconds': remaining,
                'elapsed_seconds': elapsed,
                'speed_deg_per_sec': mv.speed_deg_per_sec
            }

    def set_position(self, position: float) -> None:
        """
        Définit la position directement (sans mouvement).
        Arrête tout mouvement en cours.
        """
        with self._movement_lock:
            self._current_movement = None
            self._position = position % 360

    def wait_for_completion(self, timeout: float = None) -> bool:
        """
        Attend la fin du mouvement en cours.

        Args:
            timeout: Timeout en secondes (None = attendre indéfiniment)

        Returns:
            True si le mouvement est terminé, False si timeout
        """
        start = time.time()
        while self.is_moving():
            if timeout and (time.time() - start) > timeout:
                return False
            time.sleep(0.05)
        return True


# Instance singleton globale du simulateur
_movement_simulator: Optional[MovementSimulator] = None


def get_movement_simulator() -> MovementSimulator:
    """Retourne l'instance singleton du MovementSimulator."""
    global _movement_simulator
    if _movement_simulator is None:
        _movement_simulator = MovementSimulator()
    return _movement_simulator


# =============================================================================
# HELPER FUNCTIONS - Compatibilité avec l'API existante
# =============================================================================

def set_simulated_position(position: float):
    """Permet de synchroniser la position simulée depuis l'extérieur."""
    get_movement_simulator().set_position(position)


def get_simulated_position() -> float:
    """Retourne la position simulée actuelle (interpolée si mouvement en cours)."""
    return get_movement_simulator().get_current_position()


# Variable globale legacy pour compatibilité (lecture seule recommandée)
_simulated_position = 0.0


# =============================================================================
# MOTEUR SIMULÉ
# =============================================================================

class MoteurSimule:
    """
    Moteur simulé pour tests.

    VERSION 4.5: Utilise MovementSimulator pour une simulation
    temporelle réaliste des mouvements.
    """

    def __init__(self, config_moteur=None):
        self.logger = logging.getLogger("MoteurSimule")

        if config_moteur:
            if hasattr(config_moteur, 'steps_per_dome_revolution'):
                self.steps_per_dome_revolution = config_moteur.steps_per_dome_revolution
            elif hasattr(config_moteur, 'steps_per_revolution'):
                # Dataclass
                self.steps_per_dome_revolution = int(
                    config_moteur.steps_per_revolution *
                    config_moteur.microsteps *
                    config_moteur.gear_ratio *
                    config_moteur.steps_correction_factor
                )
            else:
                # Dict
                self.steps_per_dome_revolution = int(
                    config_moteur['steps_per_revolution'] *
                    config_moteur['microsteps'] *
                    config_moteur['gear_ratio'] *
                    config_moteur['steps_correction_factor']
                )
        else:
            self.steps_per_dome_revolution = 1941866  # Valeur calculée

        # Configurer le simulateur avec les bons paramètres
        self._simulator = get_movement_simulator()
        self._simulator.set_steps_per_revolution(self.steps_per_dome_revolution)

        # Position initiale depuis le simulateur
        self.position_actuelle = self._simulator.get_current_position()

        # Direction actuelle (1 = horaire, -1 = anti-horaire)
        self.direction = 1

        # Flag pour arrêt non bloquant de la boucle feedback
        self.stop_requested = False

        # Paramètres rampe (pour compatibilité)
        self.ramp_start_delay = 0.003
        self.ramp_steps = 400  # Aligné avec moteur.py
        self.ramp_enabled = True

        # Degrés par pas (pour simulation réaliste)
        self.degrees_per_step = 360.0 / self.steps_per_dome_revolution

        self.logger.info(f"Moteur SIMULÉ v4.5 initialisé - Steps/tour: {self.steps_per_dome_revolution}")

    def definir_direction(self, direction: int):
        """Définit la direction de rotation."""
        self.direction = direction

    def faire_un_pas(self, delai: float = 0.0):
        """
        Simule un pas moteur.

        Note: En mode simulation avec MovementSimulator, cette méthode
        n'est généralement pas utilisée car rotation() gère tout le mouvement.
        """
        # Calculer le déplacement en degrés
        delta = self.degrees_per_step * self.direction

        # Appliquer le pas via le simulateur
        current = self._simulator.get_current_position()
        self._simulator.set_position(current + delta)
        self.position_actuelle = self._simulator.get_current_position()

    def _calculer_delai_rampe(self, step_index: int, total_steps: int,
                               vitesse_nominale: float) -> float:
        """Calcule le délai pour un pas (retourne toujours la vitesse nominale en simulation)."""
        return vitesse_nominale

    def rotation(self, angle_deg: float, vitesse: float = 0.0015):
        """
        Simule une rotation avec timing réaliste.

        La position est interpolée en fonction du temps écoulé,
        simulant ainsi le comportement réel du moteur.

        Args:
            angle_deg: Angle de rotation en degrés (signé)
            vitesse: Délai moteur en secondes (motor_delay)
        """
        self._simulator.start_movement(angle_deg, vitesse)

        # Attendre la fin du mouvement (simulation réaliste)
        # Vérifier stop_requested périodiquement
        while self._simulator.is_moving():
            if self.stop_requested:
                self._simulator.stop_movement()
                break
            time.sleep(0.05)

        self.position_actuelle = self._simulator.get_current_position()

    def rotation_absolue(self, position_cible_deg: float, position_actuelle_deg: float,
                        vitesse: float = 0.0015):
        """Rotation vers une position absolue."""
        position_cible = position_cible_deg % 360
        position_actuelle = position_actuelle_deg % 360

        diff = position_cible - position_actuelle
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360

        self.rotation(diff, vitesse)

    # =========================================================================
    # MÉTHODES DÉMON (simulées)
    # =========================================================================

    @staticmethod
    def get_daemon_angle(timeout_ms: int = 200) -> float:
        """Retourne la position simulée (interpolée si mouvement en cours)."""
        return get_movement_simulator().get_current_position()

    @staticmethod
    def get_daemon_status() -> Optional[dict]:
        """Retourne un statut simulé."""
        simulator = get_movement_simulator()
        movement_info = simulator.get_movement_info()

        status = {
            'angle': simulator.get_current_position(),
            'calibrated': True,
            'status': 'OK (simulation)',
            'timestamp': 0
        }

        # Ajouter les infos de mouvement si en cours
        if movement_info:
            status['moving'] = True
            status['movement'] = movement_info
        else:
            status['moving'] = False

        return status

    # =========================================================================
    # CONTRÔLE D'ARRÊT
    # =========================================================================

    def request_stop(self):
        """
        Demande l'arrêt de la boucle de feedback en cours.
        Cette méthode est non bloquante et permet d'arrêter
        la correction en cours sans attendre la fin de toutes les itérations.
        """
        self.stop_requested = True
        self._simulator.stop_movement()

    def clear_stop_request(self):
        """
        Efface le flag d'arrêt pour permettre de nouvelles corrections.
        """
        self.stop_requested = False

    def rotation_avec_feedback(
        self,
        angle_cible: float,
        vitesse: float = 0.001,
        tolerance: float = 0.5,
        max_iterations: int = 10,
        max_correction_par_iteration: float = 45.0
    ) -> Dict[str, Any]:
        """
        Simule une rotation avec feedback et timing réaliste.

        Le mouvement prend le temps réel qu'il prendrait sur le matériel.
        """
        start_time = time.time()
        position_initiale = self._simulator.get_current_position()

        # Calculer le delta
        delta = angle_cible - position_initiale
        while delta > 180:
            delta -= 360
        while delta < -180:
            delta += 360

        # Appliquer le mouvement avec timing réaliste
        self.rotation(delta, vitesse)

        temps_total = time.time() - start_time
        position_finale = self._simulator.get_current_position()

        return {
            'success': True,
            'position_initiale': position_initiale,
            'position_finale': position_finale,
            'position_cible': angle_cible,
            'erreur_finale': 0.0,
            'iterations': 1,
            'corrections': [],
            'temps_total': temps_total,
            'mode': 'simulation'
        }

    def rotation_relative_avec_feedback(
        self,
        delta_deg: float,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Simule une rotation relative avec feedback.
        """
        angle_cible = (self._simulator.get_current_position() + delta_deg) % 360
        return self.rotation_avec_feedback(angle_cible=angle_cible, **kwargs)

    # =========================================================================
    # FEEDBACK CONTROLLER (simulé)
    # =========================================================================

    def get_feedback_controller(self):
        """
        Retourne un contrôleur de feedback simulé.

        En simulation, retourne self car les méthodes de feedback
        sont déjà implémentées dans cette classe.
        """
        return self

    def nettoyer(self):
        pass


# =============================================================================
# SIMULATED DAEMON READER - Pour compatibilité avec l'architecture IPC
# =============================================================================

class SimulatedDaemonReader:
    """
    Lecteur simulé pour le daemon encodeur.

    En mode simulation, lit la position depuis MovementSimulator
    au lieu du fichier /dev/shm/ems22_position.json.
    """

    def __init__(self):
        self.logger = logging.getLogger("SimulatedDaemonReader")
        self._simulator = get_movement_simulator()

    def is_available(self) -> bool:
        """Toujours disponible en simulation."""
        return True

    def read_raw(self) -> dict:
        """Retourne un statut simulé."""
        return {
            'angle': self._simulator.get_current_position(),
            'calibrated': True,
            'status': 'OK (simulation)',
            'raw': 0
        }

    def read_angle(self, timeout_ms: int = 200) -> float:
        """Retourne la position simulée (interpolée si mouvement en cours)."""
        return self._simulator.get_current_position()

    def read_status(self) -> dict:
        """Retourne le statut complet simulé."""
        return self.read_raw()

    def read_stable(self, num_samples: int = 3, delay_ms: int = 10,
                    stabilization_ms: int = 50) -> float:
        """Retourne la position simulée (pas de moyennage nécessaire)."""
        return self.read_angle()
