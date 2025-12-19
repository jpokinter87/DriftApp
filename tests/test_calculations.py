"""
Tests pour le module core/observatoire/calculations.py

Ce module teste les calculs astronomiques: conversions de coordonnées,
parallaxe, temps sidéral, etc.
"""

import math
import pytest
from datetime import datetime, timedelta, timezone


class TestAstronomicalCalculationsInit:
    """Tests pour l'initialisation de AstronomicalCalculations."""

    def test_init_parametres_defaut(self):
        """Initialisation avec paramètres par défaut."""
        from core.observatoire.calculations import AstronomicalCalculations

        calc = AstronomicalCalculations(
            latitude=44.15,
            longitude=5.23,
            tz_offset=1
        )
        assert calc.latitude == 44.15
        assert calc.longitude == 5.23
        assert calc.tz_offset == 1
        assert calc.deport_tube == 0.40  # Défaut
        assert calc.rayon_coupole == 1.20  # Défaut

    def test_init_parametres_personnalises(self):
        """Initialisation avec paramètres personnalisés."""
        from core.observatoire.calculations import AstronomicalCalculations

        calc = AstronomicalCalculations(
            latitude=48.85,
            longitude=2.35,
            tz_offset=2,
            deport_tube=0.50,
            rayon_coupole=1.50
        )
        assert calc.deport_tube == 0.50
        assert calc.rayon_coupole == 1.50


class TestNormalisationAngles:
    """Tests pour les méthodes de normalisation."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_normaliser_angle_180_positif(self, calc):
        """Normalisation vers [-180, 180] - angles positifs."""
        assert calc._normaliser_angle_180(0) == 0
        assert calc._normaliser_angle_180(90) == 90
        assert calc._normaliser_angle_180(180) == 180
        assert calc._normaliser_angle_180(270) == -90
        assert calc._normaliser_angle_180(360) == 0

    def test_normaliser_angle_180_negatif(self, calc):
        """Normalisation vers [-180, 180] - angles négatifs."""
        assert calc._normaliser_angle_180(-90) == -90
        assert calc._normaliser_angle_180(-180) == 180
        assert calc._normaliser_angle_180(-270) == 90

    def test_normaliser_angle_360(self, calc):
        """Normalisation vers [0, 360]."""
        assert calc._normaliser_angle_360(0) == 0
        assert calc._normaliser_angle_360(90) == 90
        assert calc._normaliser_angle_360(360) == 0
        assert calc._normaliser_angle_360(370) == 10
        assert calc._normaliser_angle_360(-10) == 350


class TestConversionJ2000JNOW:
    """Tests pour la conversion J2000 vers JNOW."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_conversion_basique(self, calc):
        """Conversion de coordonnées J2000 vers JNOW."""
        # Vega: coordonnées J2000
        ad_j2000 = 279.23
        dec_j2000 = 38.78
        date = datetime(2025, 6, 21, 22, 0, 0, tzinfo=timezone.utc)

        ad_jnow, dec_jnow = calc.convertir_j2000_vers_jnow(ad_j2000, dec_j2000, date)

        # La précession est faible sur quelques années
        assert abs(ad_jnow - ad_j2000) < 1.0  # < 1° de différence
        assert abs(dec_jnow - dec_j2000) < 0.5  # < 0.5° de différence

    def test_conversion_avec_datetime_naive(self, calc):
        """Conversion avec datetime naive (sans timezone)."""
        ad_j2000 = 250.42
        dec_j2000 = 36.46
        date = datetime(2025, 6, 21, 23, 0, 0)  # Naive

        ad_jnow, dec_jnow = calc.convertir_j2000_vers_jnow(ad_j2000, dec_j2000, date)

        assert isinstance(ad_jnow, float)
        assert isinstance(dec_jnow, float)

    def test_conversion_polaris(self, calc):
        """Conversion pour Polaris (haute déclinaison)."""
        # Polaris: très proche du pôle nord céleste
        ad_j2000 = 37.95
        dec_j2000 = 89.26
        date = datetime(2025, 6, 21, 22, 0, 0, tzinfo=timezone.utc)

        ad_jnow, dec_jnow = calc.convertir_j2000_vers_jnow(ad_j2000, dec_j2000, date)

        # La déclinaison reste proche du pôle
        assert dec_jnow > 88.0


class TestCorrectionParallaxe:
    """Tests pour la correction de parallaxe."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(
            latitude=44.15,
            longitude=5.23,
            tz_offset=1,
            deport_tube=0.40,
            rayon_coupole=1.20
        )

    def test_parallaxe_zenith_nulle(self, calc):
        """Au zénith, la correction est nulle."""
        correction = calc.calculer_correction_parallaxe(180.0, 90.0)
        assert correction == pytest.approx(0.0, abs=0.01)

    def test_parallaxe_est_positive(self, calc):
        """Correction positive à l'Est."""
        correction = calc.calculer_correction_parallaxe(90.0, 45.0)
        assert correction > 0

    def test_parallaxe_ouest_negative(self, calc):
        """Correction négative à l'Ouest."""
        correction = calc.calculer_correction_parallaxe(270.0, 45.0)
        assert correction < 0

    def test_symetrie_est_ouest(self, calc):
        """Symétrie Est/Ouest des corrections."""
        for altitude in [15, 30, 45, 60, 75]:
            corr_est = calc.calculer_correction_parallaxe(90.0, altitude)
            corr_ouest = calc.calculer_correction_parallaxe(270.0, altitude)
            # Les corrections doivent être opposées
            assert abs(corr_est + corr_ouest) < 0.01

    def test_parallaxe_diminue_avec_altitude(self, calc):
        """La parallaxe diminue quand l'altitude augmente."""
        corr_15 = abs(calc.calculer_correction_parallaxe(90.0, 15.0))
        corr_45 = abs(calc.calculer_correction_parallaxe(90.0, 45.0))
        corr_75 = abs(calc.calculer_correction_parallaxe(90.0, 75.0))

        assert corr_15 > corr_45 > corr_75

    def test_parallaxe_nord_sud_faible(self, calc):
        """Correction plus faible au Nord et au Sud."""
        corr_nord = abs(calc.calculer_correction_parallaxe(0.0, 45.0))
        corr_est = abs(calc.calculer_correction_parallaxe(90.0, 45.0))

        # La correction Est doit être plus grande
        assert corr_est > corr_nord

    def test_valider_symetrie(self, calc):
        """Test de la méthode de validation de symétrie."""
        assert calc.valider_symetrie(tolerance=0.1)


class TestTempsSideral:
    """Tests pour le calcul du temps sidéral."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_temps_sideral_type(self, calc):
        """Le temps sidéral est un float en degrés."""
        date = datetime(2025, 6, 21, 22, 0, 0)
        lst = calc.calculer_temps_sideral(date)

        assert isinstance(lst, float)
        assert 0 <= lst < 360

    def test_temps_sideral_avance_avec_temps(self, calc):
        """Le temps sidéral avance plus vite que le temps solaire."""
        date1 = datetime(2025, 6, 21, 22, 0, 0)
        date2 = datetime(2025, 6, 21, 23, 0, 0)  # 1 heure plus tard

        lst1 = calc.calculer_temps_sideral(date1)
        lst2 = calc.calculer_temps_sideral(date2)

        # ~15° par heure solaire, légèrement plus pour le temps sidéral
        diff = (lst2 - lst1) % 360
        assert 14 < diff < 16

    def test_jour_julien(self, calc):
        """Test du calcul du jour julien."""
        # J2000.0 = 1er janvier 2000 à 12h TU
        date = datetime(2000, 1, 1, 12, 0, 0)
        jd = calc._calculate_julian_day(date)

        assert jd == pytest.approx(2451545.0, abs=0.01)


class TestAngleHoraire:
    """Tests pour le calcul de l'angle horaire."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_angle_horaire_type(self, calc):
        """L'angle horaire est entre -180 et +180."""
        date = datetime(2025, 6, 21, 22, 0, 0)
        ha = calc.calculer_angle_horaire(250.0, date)

        assert -180 <= ha <= 180

    def test_angle_horaire_passage_meridien(self, calc):
        """Angle horaire nul au passage au méridien."""
        date = datetime(2025, 6, 21, 22, 0, 0)
        lst = calc.calculer_temps_sideral(date)

        # Objet au méridien: AD = LST
        ha = calc.calculer_angle_horaire(lst, date, deja_jnow=True)
        assert ha == pytest.approx(0.0, abs=0.1)


class TestCoordonneesHorizontales:
    """Tests pour la conversion en coordonnées horizontales."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_coords_horizontales_type(self, calc):
        """Azimut et altitude sont des floats."""
        date = datetime(2025, 6, 21, 22, 0, 0)
        az, alt = calc.calculer_coords_horizontales(250.0, 36.0, date)

        assert isinstance(az, float)
        assert isinstance(alt, float)

    def test_coords_horizontales_plages(self, calc):
        """Azimut [0, 360], altitude [-90, 90]."""
        date = datetime(2025, 6, 21, 22, 0, 0)
        az, alt = calc.calculer_coords_horizontales(250.0, 36.0, date)

        assert 0 <= az < 360
        assert -90 <= alt <= 90

    def test_polaris_haute_altitude(self, calc):
        """Polaris est toujours haute pour un observateur nordique."""
        # Polaris: DEC ~89.26°, toujours visible depuis latitude 44°
        date = datetime(2025, 6, 21, 22, 0, 0)
        az, alt = calc.calculer_coords_horizontales(37.95, 89.26, date)

        # Altitude de Polaris ≈ latitude de l'observateur
        assert alt > 40

    def test_coords_coupole_avec_correction(self, calc):
        """calculer_coords_horizontales_coupole inclut la correction."""
        date = datetime(2025, 6, 21, 22, 0, 0)

        az_coupole, alt, correction = calc.calculer_coords_horizontales_coupole(
            250.0, 36.0, date
        )

        assert isinstance(correction, float)
        assert 0 <= az_coupole < 360


class TestRefractionAtmospherique:
    """Tests pour la correction de réfraction."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_refraction_augmente_altitude(self, calc):
        """La réfraction augmente l'altitude apparente."""
        alt_geometrique = 10.0
        alt_apparente = calc._apply_refraction_correction(alt_geometrique)

        assert alt_apparente > alt_geometrique

    def test_refraction_plus_forte_horizon(self, calc):
        """La réfraction est plus forte près de l'horizon."""
        corr_5 = calc._apply_refraction_correction(5.0) - 5.0
        corr_45 = calc._apply_refraction_correction(45.0) - 45.0

        assert corr_5 > corr_45

    def test_refraction_negligeable_zenith(self, calc):
        """Réfraction négligeable au zénith."""
        alt = 89.0
        corr = calc._apply_refraction_correction(alt) - alt

        assert corr < 0.1  # < 0.1° au zénith

    def test_pas_de_refraction_sous_horizon(self, calc):
        """Pas de correction sous l'horizon."""
        alt = -5.0
        result = calc._apply_refraction_correction(alt)

        assert result == alt


class TestPassageMeridien:
    """Tests pour le calcul du passage au méridien."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_est_proche_meridien(self, calc):
        """Détection de proximité au méridien."""
        date = datetime(2025, 6, 21, 22, 0, 0)
        lst = calc.calculer_temps_sideral(date)

        # Objet exactement au méridien
        est_proche, temps = calc.est_proche_meridien(lst, date, seuil_minutes=5)
        assert est_proche
        assert abs(temps) < 300  # < 5 minutes

    def test_heure_passage_meridien(self, calc):
        """Calcul de l'heure de passage."""
        date = datetime(2025, 6, 21, 12, 0, 0)

        passage = calc.calculer_heure_passage_meridien(250.0, date)

        assert isinstance(passage, datetime)
        assert passage.date() == date.date()


class TestVitesseRotationCoupole:
    """Tests pour le calcul de vitesse de rotation."""

    @pytest.fixture
    def calc(self):
        from core.observatoire.calculations import AstronomicalCalculations
        return AstronomicalCalculations(44.15, 5.23, 1)

    def test_vitesse_rotation_type(self, calc):
        """Retourne un tuple de 4 éléments."""
        date = datetime(2025, 6, 21, 22, 0, 0)

        result = calc.calculer_vitesse_rotation_coupole(250.0, 36.0, date)

        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_vitesse_rotation_valeurs(self, calc):
        """Vérifie les types des valeurs retournées."""
        date = datetime(2025, 6, 21, 22, 0, 0)

        vitesse_rel, sens, az, alt = calc.calculer_vitesse_rotation_coupole(
            250.0, 36.0, date
        )

        assert isinstance(vitesse_rel, float)
        assert sens in [-1, 1]
        assert 0 <= az < 360
        assert -90 <= alt <= 90

    def test_vitesse_relative_petite(self, calc):
        """La vitesse relative est une fraction de tour/heure."""
        date = datetime(2025, 6, 21, 22, 0, 0)

        vitesse_rel, _, _, _ = calc.calculer_vitesse_rotation_coupole(
            250.0, 36.0, date
        )

        # Vitesse typique: quelques pour cent de tour par heure
        assert vitesse_rel < 0.1
