"""
Tests pour le module core/tracking/abaque_manager.py

Ce module teste le gestionnaire d'abaque pour l'interpolation
des positions de coupole basées sur les mesures empiriques.
"""

import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestAbaqueManagerInit:
    """Tests pour l'initialisation de AbaqueManager."""

    def test_init_defaut(self):
        """Initialisation avec chemin par défaut."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        assert manager.abaque_file == Path("data/Loi_coupole.xlsx")
        assert manager.is_loaded is False
        assert manager.data_by_altitude == {}

    def test_init_chemin_personnalise(self):
        """Initialisation avec chemin personnalisé."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager("custom/path/abaque.xlsx")
        assert manager.abaque_file == Path("custom/path/abaque.xlsx")

    def test_init_statistiques_zero(self):
        """Statistiques initialisées à zéro."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        assert manager.n_altitudes == 0
        assert manager.n_azimuths == 0
        assert manager.altitude_range == (0.0, 0.0)
        assert manager.azimuth_range == (0.0, 0.0)


class TestAbaqueManagerLoadAbaque:
    """Tests pour le chargement de l'abaque."""

    def test_load_fichier_inexistant(self):
        """Retourne False si fichier n'existe pas."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager("/chemin/inexistant/abaque.xlsx")
        result = manager.load_abaque()

        assert result is False
        assert manager.is_loaded is False

    @patch('core.tracking.abaque_manager.openpyxl.load_workbook')
    def test_load_erreur_lecture(self, mock_load_workbook):
        """Retourne False en cas d'erreur de lecture."""
        from core.tracking.abaque_manager import AbaqueManager

        mock_load_workbook.side_effect = Exception("Erreur de lecture")

        manager = AbaqueManager()
        # Simuler que le fichier existe
        with patch.object(Path, 'exists', return_value=True):
            result = manager.load_abaque()

        assert result is False

    def test_load_abaque_reel(self):
        """Charge l'abaque réelle si disponible."""
        from core.tracking.abaque_manager import AbaqueManager

        abaque_path = Path("data/Loi_coupole.xlsx")
        if not abaque_path.exists():
            pytest.skip("Fichier abaque non disponible")

        manager = AbaqueManager()
        result = manager.load_abaque()

        assert result is True
        assert manager.is_loaded is True
        assert manager.n_altitudes > 0
        assert manager.n_azimuths > 0


class TestAbaqueManagerWithMockData:
    """Tests avec données d'abaque simulées."""

    @pytest.fixture
    def manager_with_data(self, sample_abaque_data):
        """Manager avec données injectées."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        manager.data_by_altitude = sample_abaque_data
        manager.is_loaded = True

        # Calculer les statistiques manuellement
        manager.n_altitudes = len(sample_abaque_data)
        first_alt = next(iter(sample_abaque_data.values()))
        manager.n_azimuths = len(first_alt['az_astre'])

        altitudes = sorted(sample_abaque_data.keys())
        manager.altitude_range = (altitudes[0], altitudes[-1])

        all_azimuths = []
        for data in sample_abaque_data.values():
            all_azimuths.extend(data['az_astre'])
        manager.azimuth_range = (min(all_azimuths), max(all_azimuths))

        # Créer les grilles
        manager._alt_grid = np.array(altitudes)
        manager._az_grid = np.array(sorted(first_alt['az_astre']))
        manager._data_dict = sample_abaque_data

        return manager

    def test_get_dome_position_in_bounds(self, manager_with_data):
        """Position dans les limites de l'abaque."""
        az_coupole, infos = manager_with_data.get_dome_position(45.0, 90.0)

        assert isinstance(az_coupole, float)
        assert 0 <= az_coupole < 360
        assert infos["in_bounds"] is True
        assert infos["method"] == "interpolation"

    def test_get_dome_position_exact_point(self, manager_with_data):
        """Position exactement sur un point mesuré."""
        # Altitude 45°, Azimut 90° → devrait donner 96°
        az_coupole, infos = manager_with_data.get_dome_position(45.0, 90.0)

        assert az_coupole == pytest.approx(96.0, abs=0.5)

    def test_get_dome_position_interpolated(self, manager_with_data):
        """Position interpolée entre deux points."""
        # Entre altitude 30° et 45°, azimut 90°
        az_coupole, infos = manager_with_data.get_dome_position(37.5, 90.0)

        # Devrait être entre 95° (alt=30) et 96° (alt=45)
        assert 95.0 <= az_coupole <= 96.0

    def test_get_dome_position_normalise_azimut(self, manager_with_data):
        """L'azimut est normalisé dans [0, 360)."""
        az_coupole1, _ = manager_with_data.get_dome_position(45.0, 90.0)
        az_coupole2, _ = manager_with_data.get_dome_position(45.0, 450.0)  # 450 = 90

        assert az_coupole1 == pytest.approx(az_coupole2, abs=0.1)

    def test_get_dome_position_not_loaded_raises(self):
        """Lève une exception si abaque non chargée."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        # is_loaded = False par défaut

        with pytest.raises(RuntimeError, match="Abaque non chargée"):
            manager.get_dome_position(45.0, 90.0)


class TestAbaqueManagerNearestNeighbor:
    """Tests pour la méthode nearest_neighbor."""

    @pytest.fixture
    def manager_with_data(self, sample_abaque_data):
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        manager.data_by_altitude = sample_abaque_data
        manager.is_loaded = True
        return manager

    def test_nearest_neighbor_exact_match(self, manager_with_data):
        """Trouve le point exact si disponible."""
        result = manager_with_data._nearest_neighbor(45.0, 90.0)

        # Point exact: alt=45, az=90 → az_coupole=96
        assert result == 96.0

    def test_nearest_neighbor_proche(self, manager_with_data):
        """Trouve le point le plus proche."""
        result = manager_with_data._nearest_neighbor(46.0, 91.0)

        # Le plus proche est alt=45, az=90 → 96
        assert result == pytest.approx(96.0, abs=1.0)


class TestAbaqueManagerDiagnostics:
    """Tests pour les diagnostics."""

    def test_diagnostics_not_loaded(self):
        """Diagnostics quand abaque non chargée."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        result = manager.get_diagnostics()

        assert result["status"] == "not_loaded"
        assert "message" in result

    @pytest.fixture
    def loaded_manager(self, sample_abaque_data):
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        manager.data_by_altitude = sample_abaque_data
        manager.is_loaded = True
        manager.n_altitudes = 4
        manager.n_azimuths = 8
        manager.altitude_range = (30.0, 75.0)
        manager.azimuth_range = (0.0, 315.0)
        return manager

    def test_diagnostics_loaded(self, loaded_manager):
        """Diagnostics quand abaque chargée."""
        result = loaded_manager.get_diagnostics()

        assert result["status"] == "loaded"
        assert "statistics" in result
        assert result["statistics"]["n_altitudes"] == 4
        assert result["statistics"]["n_azimuths"] == 8
        assert "altitudes_available" in result


class TestAbaqueManagerExport:
    """Tests pour l'export JSON."""

    def test_export_not_loaded(self):
        """Export échoue si abaque non chargée."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        result = manager.export_to_json("/tmp/test_export.json")

        assert result is False

    @pytest.fixture
    def loaded_manager(self, sample_abaque_data, tmp_path):
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        manager.data_by_altitude = sample_abaque_data
        manager.is_loaded = True
        manager.n_altitudes = 4
        manager.n_azimuths = 8
        manager.altitude_range = (30.0, 75.0)
        manager.azimuth_range = (0.0, 315.0)
        manager.abaque_file = Path("test.xlsx")
        return manager, tmp_path

    def test_export_success(self, loaded_manager):
        """Export réussit avec données valides."""
        manager, tmp_path = loaded_manager
        output_file = tmp_path / "export.json"

        result = manager.export_to_json(str(output_file))

        assert result is True
        assert output_file.exists()

        # Vérifier le contenu
        with open(output_file) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "data" in data
        assert data["metadata"]["n_altitudes"] == 4


class TestAbaqueManagerInterpolation:
    """Tests détaillés pour l'interpolation circulaire."""

    @pytest.fixture
    def manager_with_data(self, sample_abaque_data):
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        manager.data_by_altitude = sample_abaque_data
        manager.is_loaded = True

        altitudes = sorted(sample_abaque_data.keys())
        first_alt = sample_abaque_data[altitudes[0]]
        azimuths = sorted(first_alt['az_astre'])

        manager._alt_grid = np.array(altitudes)
        manager._az_grid = np.array(azimuths)
        manager._data_dict = sample_abaque_data

        return manager

    def test_interpolation_milieu_cellule(self, manager_with_data):
        """Interpolation au milieu d'une cellule."""
        # Point au centre de la cellule [30-45, 45-90]
        result = manager_with_data._interpolate_circular(37.5, 67.5)

        # Moyenne approximative des 4 coins
        # Corners: (30,45)=47, (30,90)=95, (45,45)=48, (45,90)=96
        # Moyenne ≈ 71.5
        assert 65 < result < 80

    def test_interpolation_bord_grille(self, manager_with_data):
        """Interpolation au bord de la grille."""
        # À la limite basse de la grille
        result = manager_with_data._interpolate_circular(30.0, 45.0)

        # Point exact: devrait être 47
        assert result == pytest.approx(47.0, abs=1.0)

    def test_interpolation_gestion_circularite(self):
        """Test de la gestion des angles circulaires."""
        from core.tracking.abaque_manager import AbaqueManager

        # Créer des données avec passage par 0°/360°
        data = {
            30.0: {
                'az_astre': [350, 10],
                'az_coupole': [355, 5]  # Traverse 0°
            },
            45.0: {
                'az_astre': [350, 10],
                'az_coupole': [356, 6]
            }
        }

        manager = AbaqueManager()
        manager.data_by_altitude = data
        manager.is_loaded = True
        manager._alt_grid = np.array([30.0, 45.0])
        manager._az_grid = np.array([350, 10])
        manager._data_dict = data

        # Interpoler à az=0 (milieu de 350-10)
        result = manager._interpolate_circular(37.5, 0)

        # Devrait être proche de 0° (milieu de 355-5 et 356-6)
        assert result < 10 or result > 350


class TestAbaqueManagerComputeStatistics:
    """Tests pour le calcul des statistiques."""

    def test_compute_statistics_empty(self):
        """Statistiques vides si pas de données."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        manager._compute_statistics()

        # Pas d'erreur, mais rien n'est calculé
        assert manager.n_altitudes == 0

    def test_compute_statistics_with_data(self, sample_abaque_data):
        """Calcul correct des statistiques."""
        from core.tracking.abaque_manager import AbaqueManager

        manager = AbaqueManager()
        manager.data_by_altitude = sample_abaque_data
        manager._compute_statistics()

        assert manager.n_altitudes == 4
        assert manager.n_azimuths == 8
        assert manager.altitude_range == (30.0, 75.0)
        assert manager.azimuth_range == (0, 315)
