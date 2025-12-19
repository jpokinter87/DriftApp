"""
Tests pour le module core/utils/angle_utils.py

Ce module teste les fonctions utilitaires de calcul angulaire.
"""

import pytest
from core.utils.angle_utils import (
    normalize_angle_360,
    normalize_angle_180,
    shortest_angular_distance,
    angles_are_close,
    calculate_rotation_direction,
    calculate_steps_for_rotation
)


class TestNormalizeAngle360:
    """Tests pour normalize_angle_360."""

    def test_angle_normal(self):
        """Angle déjà dans [0, 360) reste inchangé."""
        assert normalize_angle_360(45.0) == 45.0
        assert normalize_angle_360(180.0) == 180.0
        assert normalize_angle_360(0.0) == 0.0
        assert normalize_angle_360(359.9) == pytest.approx(359.9)

    def test_angle_superieur_360(self):
        """Angles > 360 sont ramenés dans l'intervalle."""
        assert normalize_angle_360(370.0) == 10.0
        assert normalize_angle_360(720.0) == 0.0
        assert normalize_angle_360(450.0) == 90.0
        assert normalize_angle_360(365.5) == pytest.approx(5.5)

    def test_angle_negatif(self):
        """Angles négatifs sont ramenés dans l'intervalle."""
        assert normalize_angle_360(-10.0) == 350.0
        assert normalize_angle_360(-90.0) == 270.0
        assert normalize_angle_360(-360.0) == 0.0
        assert normalize_angle_360(-370.0) == 350.0

    def test_angle_360_exact(self):
        """360° devient 0°."""
        assert normalize_angle_360(360.0) == 0.0

    def test_tres_grands_angles(self):
        """Très grands angles positifs et négatifs."""
        assert normalize_angle_360(1080.0) == 0.0  # 3 tours complets
        assert normalize_angle_360(-1080.0) == 0.0
        assert normalize_angle_360(1085.0) == 5.0


class TestNormalizeAngle180:
    """Tests pour normalize_angle_180."""

    def test_angle_deja_dans_intervalle(self):
        """Angle déjà dans [-180, 180] reste inchangé."""
        assert normalize_angle_180(0.0) == 0.0
        assert normalize_angle_180(90.0) == 90.0
        assert normalize_angle_180(-90.0) == -90.0
        assert normalize_angle_180(180.0) == 180.0

    def test_angle_superieur_180(self):
        """Angles > 180 sont ramenés vers le négatif."""
        assert normalize_angle_180(270.0) == -90.0
        assert normalize_angle_180(200.0) == -160.0
        assert normalize_angle_180(359.0) == -1.0

    def test_angle_negatif_inferieur_moins180(self):
        """Angles < -180 sont ramenés vers le positif."""
        assert normalize_angle_180(-270.0) == 90.0
        assert normalize_angle_180(-200.0) == 160.0

    def test_cas_limites(self):
        """Cas limites aux frontières."""
        assert normalize_angle_180(180.0) == 180.0  # Reste 180
        assert normalize_angle_180(-180.0) == 180.0  # -180 % 360 = 180


class TestShortestAngularDistance:
    """Tests pour shortest_angular_distance."""

    def test_distance_directe_positive(self):
        """Distance directe dans le sens horaire."""
        assert shortest_angular_distance(0.0, 90.0) == 90.0
        assert shortest_angular_distance(10.0, 50.0) == 40.0

    def test_distance_directe_negative(self):
        """Distance directe dans le sens anti-horaire."""
        assert shortest_angular_distance(90.0, 0.0) == -90.0
        assert shortest_angular_distance(50.0, 10.0) == -40.0

    def test_traversee_zero(self):
        """Traversée de 0°/360°."""
        assert shortest_angular_distance(350.0, 10.0) == 20.0
        assert shortest_angular_distance(10.0, 350.0) == -20.0

    def test_chemin_long_vs_court(self):
        """Choix du chemin le plus court."""
        # De 10° à 300°: chemin court = -70°, pas +290°
        assert shortest_angular_distance(10.0, 300.0) == -70.0
        # De 300° à 10°: chemin court = +70°, pas -290°
        assert shortest_angular_distance(300.0, 10.0) == 70.0

    def test_angle_180_ambigu(self):
        """Angle de 180° (ambigu, les deux chemins sont égaux)."""
        result = shortest_angular_distance(0.0, 180.0)
        assert result == 180.0  # Selon l'implémentation

    def test_angles_identiques(self):
        """Angles identiques → distance nulle."""
        assert shortest_angular_distance(45.0, 45.0) == 0.0
        assert shortest_angular_distance(0.0, 360.0) == 0.0

    def test_precision_flottants(self):
        """Précision avec nombres à virgule flottante."""
        result = shortest_angular_distance(359.999, 0.001)
        assert result == pytest.approx(0.002, abs=0.001)


class TestAnglesAreClose:
    """Tests pour angles_are_close."""

    def test_angles_proches(self):
        """Angles dans la tolérance."""
        assert angles_are_close(45.0, 45.3, tolerance=0.5)
        assert angles_are_close(90.0, 89.7, tolerance=0.5)

    def test_angles_eloignes(self):
        """Angles hors tolérance."""
        assert not angles_are_close(45.0, 46.0, tolerance=0.5)
        assert not angles_are_close(10.0, 11.0, tolerance=0.5)

    def test_traversee_zero(self):
        """Comparaison autour de 0°/360°."""
        assert angles_are_close(359.8, 0.2, tolerance=0.5)
        assert angles_are_close(0.1, 359.9, tolerance=0.5)
        assert not angles_are_close(359.0, 1.0, tolerance=0.5)

    def test_tolerance_par_defaut(self):
        """Tolérance par défaut de 0.5°."""
        assert angles_are_close(100.0, 100.4)
        assert not angles_are_close(100.0, 100.6)

    def test_angles_identiques(self):
        """Angles exactement identiques."""
        assert angles_are_close(45.0, 45.0, tolerance=0.1)
        assert angles_are_close(0.0, 0.0, tolerance=0.001)


class TestCalculateRotationDirection:
    """Tests pour calculate_rotation_direction."""

    def test_sens_horaire(self):
        """Rotation dans le sens horaire (positif)."""
        assert calculate_rotation_direction(0.0, 90.0) == 1
        assert calculate_rotation_direction(350.0, 10.0) == 1

    def test_sens_antihoraire(self):
        """Rotation dans le sens anti-horaire (négatif)."""
        assert calculate_rotation_direction(90.0, 0.0) == -1
        assert calculate_rotation_direction(10.0, 350.0) == -1

    def test_pas_de_rotation(self):
        """Angles identiques → pas de rotation."""
        assert calculate_rotation_direction(45.0, 45.0) == 0
        assert calculate_rotation_direction(0.0, 360.0) == 0

    def test_quasi_identiques(self):
        """Angles quasi-identiques (< 0.001°)."""
        assert calculate_rotation_direction(45.0, 45.0005) == 0


class TestCalculateStepsForRotation:
    """Tests pour calculate_steps_for_rotation."""

    def test_rotation_complete(self):
        """360° = nombre total de pas."""
        steps_per_rev = 200 * 4 * 2230  # ~1 785 600 pas
        result = calculate_steps_for_rotation(360.0, steps_per_rev)
        assert result == steps_per_rev

    def test_demi_tour(self):
        """180° = moitié des pas."""
        steps_per_rev = 1000
        result = calculate_steps_for_rotation(180.0, steps_per_rev)
        assert result == 500

    def test_petit_angle(self):
        """Petit angle de rotation."""
        steps_per_rev = 360000  # 1 pas par millième de degré
        result = calculate_steps_for_rotation(1.0, steps_per_rev)
        assert result == 1000

    def test_angle_negatif(self):
        """Angles négatifs donnent des pas positifs."""
        steps_per_rev = 1000
        result = calculate_steps_for_rotation(-90.0, steps_per_rev)
        assert result == 250

    def test_zero_degre(self):
        """0° = 0 pas."""
        result = calculate_steps_for_rotation(0.0, 1000)
        assert result == 0

    def test_configuration_reelle(self):
        """Configuration réelle du DriftApp."""
        # 200 steps/rev × 4 microsteps × 2230 gear ratio × 1.08849 correction
        steps_per_dome_rev = int(200 * 4 * 2230 * 1.08849)

        # Pour 1° de rotation de coupole
        result = calculate_steps_for_rotation(1.0, steps_per_dome_rev)
        expected = steps_per_dome_rev // 360
        assert result == expected
