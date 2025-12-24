# DriftApp - Système de Suivi Automatique de Coupole Astronomique

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.0+](https://img.shields.io/badge/django-5.0+-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org)

**Système intelligent de suivi de coupole d'observatoire** avec modes adaptatifs automatiques et feedback temps réel. Interface web responsive pour contrôle local et distant.

> **Version actuelle** : 4.5 Web - Architecture trois processus (Décembre 2025)

---

## Table des Matières

- [Vue d'ensemble](#vue-densemble)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Système Adaptatif](#système-adaptatif)
- [Interface Web](#interface-web)
- [Mode Simulation](#mode-simulation)
- [Dépannage](#dépannage)

---

## Vue d'ensemble

DriftApp est un système de suivi automatique de coupole astronomique conçu pour compenser automatiquement la rotation de la Terre et maintenir l'alignement entre le télescope et la fente de la coupole.

### Problématique

Lors d'observations astronomiques prolongées, le télescope suit l'objet céleste grâce à sa monture équatoriale, mais la coupole reste fixe. Au fil du temps, la fente de la coupole se désaligne du télescope, bloquant la vue.

### Solution DriftApp

DriftApp calcule en permanence la position optimale de la coupole en utilisant :
- **Méthode Abaque** : Interpolation à partir de ~130 mesures terrain réelles
- **Modes adaptatifs** : Ajustement automatique des paramètres selon l'altitude
- **Feedback encodeur** : Boucle fermée avec encodeur magnétique EMS22A
- **Calibration automatique** : Recalage via microswitch à 45° azimut

---

## Méthode de Calcul - Abaque

DriftApp utilise exclusivement une **méthode abaque** basée sur des mesures réelles du site.

### Interpolation à partir de mesures terrain

Le fichier `data/Loi_coupole.xlsx` contient ~130 points de mesure :
```
(Altitude, Azimut) → Position_Coupole
```

Pour une position (Alt, Az) donnée :
1. Recherche des 4 points voisins dans l'abaque
2. Interpolation bilinéaire 2D
3. Calcul de la position optimale de la coupole

**Avantages** :
- Tient compte de la réalité mécanique du site
- Compense les déformations structurelles
- Intègre les jeux mécaniques réels
- Validé par tests terrain

---

## Architecture

### Architecture Trois Processus

```
┌─────────────────────────────────────────────────────────────────┐
│                        NAVIGATEUR                                │
│                    (Interface Web)                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSUS 1: Django                          │
│                   (Interface Web + API)                          │
│  - Dashboard temps réel                                          │
│  - Catalogue objets célestes                                     │
│  - Configuration                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ IPC (JSON /dev/shm/)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PROCESSUS 2: Motor Service                      │
│                 (Contrôle moteur GPIO)                           │
│  - Commandes GOTO, JOG, CONTINUOUS                               │
│  - Tracking adaptatif                                            │
│  - Feedback boucle fermée                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Lecture JSON
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PROCESSUS 3: Encoder Daemon                      │
│                  (Lecture encodeur SPI)                          │
│  - Lecture EMS22A à 50 Hz                                        │
│  - Méthode incrémentale                                          │
│  - Calibration switch 45°                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Structure des Répertoires

```
DriftApp/
├── manage.py                      # Point d'entrée Django
├── ems22d_calibrated.py           # Démon encodeur
│
├── core/                          # Logique métier
│   ├── config/                    # Configuration
│   ├── hardware/                  # Moteur, encodeur, simulation
│   │   ├── moteur.py              # Contrôle moteur DM556T
│   │   ├── moteur_simule.py       # Simulation réaliste
│   │   └── feedback_controller.py # Boucle fermée
│   ├── tracking/                  # Logique de suivi
│   │   ├── tracker.py             # Session de tracking
│   │   ├── adaptive_tracking.py   # Système adaptatif
│   │   └── abaque_manager.py      # Interpolation abaque
│   └── observatoire/              # Calculs astronomiques
│
├── services/                      # Motor Service
│   ├── motor_service.py           # Service principal
│   ├── command_handlers.py        # Handlers GOTO/JOG/TRACKING
│   ├── ipc_manager.py             # Communication inter-processus
│   └── simulation.py              # Composants simulation
│
├── web/                           # Application Django
│   ├── settings.py                # Configuration Django
│   ├── views.py                   # Vues API
│   ├── urls.py                    # Routes
│   ├── templates/                 # Templates HTML
│   │   └── dashboard.html
│   └── static/                    # CSS, JS
│       ├── css/dashboard.css
│       └── js/dashboard.js
│
├── data/
│   ├── config.json                # Configuration
│   └── Loi_coupole.xlsx           # Abaque mesures terrain
│
└── tests/                         # Tests unitaires
```

---

## Installation

### Prérequis

- **Raspberry Pi** 4 ou 5 (Ubuntu 24.04 ou Raspberry Pi OS)
- **Python** 3.11+
- **SPI activé** pour encodeur (production)

### Installation avec `uv`

```bash
# 1. Cloner le repository
git clone https://github.com/votre-username/DriftApp.git
cd DriftApp

# 2. Installation des dépendances
uv sync

# 3. Configuration
cp data/config.example.json data/config.json
nano data/config.json

# 4. Migrations Django
uv run python manage.py migrate

# 5. (Production) Activer SPI
sudo raspi-config
# → Interface Options → SPI → Enable
```

---

## Configuration

### Configuration Matérielle

Fichier : `data/config.json`

```json
{
  "site": {
    "latitude": 44.15,
    "longitude": 5.23,
    "altitude": 800,
    "nom": "Observatoire"
  },
  "moteur": {
    "microsteps": 4,
    "steps_per_revolution": 200,
    "gear_ratio": 2230,
    "steps_correction_factor": 1.08849
  },
  "adaptive_tracking": {
    "altitudes": {
      "critical": 68.0,
      "zenith": 75.0
    },
    "modes": {
      "normal": { "interval_sec": 60, "motor_delay": 0.0011 },
      "critical": { "interval_sec": 15, "motor_delay": 0.00055 },
      "continuous": { "interval_sec": 5, "motor_delay": 0.00015 }
    }
  }
}
```

**IMPORTANT** : Le paramètre `microsteps: 4` DOIT correspondre à la configuration du driver DM556T.

---

## Utilisation

### Mode Développement (Simulation)

```bash
# Terminal 1: Lancer Django
uv run python manage.py runserver 0.0.0.0:8000

# Terminal 2: Lancer Motor Service (simulation automatique)
uv run python services/motor_service.py

# Ouvrir dans le navigateur
http://localhost:8000
```

En mode développement (sans Raspberry Pi), le système détecte automatiquement l'absence de GPIO et active le **mode simulation** avec :
- Timing réaliste des mouvements (~41°/min)
- Simulation du switch de calibration à 45°
- Position interpolée en temps réel

### Mode Production (Raspberry Pi)

```bash
# Terminal 1: Démon encodeur (sudo requis)
sudo python3 ems22d_calibrated.py &

# Terminal 2: Motor Service (sudo requis pour GPIO)
sudo python3 services/motor_service.py &

# Terminal 3: Django
uv run python manage.py runserver 0.0.0.0:8000
```

---

## Système Adaptatif

### 3 Modes Automatiques

| Mode | Déclencheur | Intervalle | Seuil | Vitesse |
|------|-------------|------------|-------|---------|
| NORMAL | Altitude < 68° | 60s | 0.5° | ~9°/min |
| CRITICAL | 68° ≤ Alt < 75° | 15s | 0.25° | ~17°/min |
| CONTINUOUS | Alt ≥ 75° ou Δ > 30° | 5s | 0.1° | ~41°/min |

### Logique de Sélection

```python
if altitude >= 75° or predicted_movement > 30°:
    mode = CONTINUOUS  # Corrections très fréquentes
elif altitude >= 68°:
    mode = CRITICAL    # Surveillance rapprochée
else:
    mode = NORMAL      # Suivi standard
```

---

## Interface Web

### Dashboard Principal

L'interface web affiche en temps réel :
- **Position encodeur** : Angle actuel de la coupole
- **État du système** : idle, moving, tracking, initializing
- **Mode adaptatif** : NORMAL / CRITICAL / CONTINUOUS
- **Objet suivi** : Nom et position (Alt/Az)
- **Statistiques** : Corrections, temps moteur

### Contrôles Disponibles

- **GOTO** : Déplacement vers une position absolue
- **JOG** : Déplacements relatifs (±1°, ±5°, ±10°)
- **CONTINUOUS** : Mouvement continu CW/CCW
- **TRACKING** : Suivi automatique d'objet céleste
- **STOP** : Arrêt d'urgence

### Popup GOTO Initial

Lors du démarrage d'un tracking, un popup affiche :
- Position actuelle et cible
- Delta avec direction (CW/CCW)
- Barre de progression
- Temps restant estimé

---

## Mode Simulation

### Fonctionnement

Le `MovementSimulator` fournit une simulation réaliste :
- **Timing réel** : Les mouvements prennent le temps qu'ils prendraient en production
- **Interpolation** : Position calculée en fonction du temps écoulé
- **Switch calibration** : Simulation du microswitch à 45°
- **Valeurs raw** : Simulation des valeurs brutes encodeur (0-1023)

### Configuration

Le mode simulation est activé automatiquement en l'absence de GPIO (développement sur PC).

Pour forcer le mode simulation sur Raspberry Pi :
```json
{
  "simulation": true
}
```

### Vitesses Simulées

| Mode | Vitesse | Temps pour 90° |
|------|---------|----------------|
| CONTINUOUS | ~1.2°/s | ~75s |
| CRITICAL | ~0.3°/s | ~5min |
| NORMAL | ~0.15°/s | ~10min |

---

## Calibration Automatique

### Switch de Calibration (45°)

Un microswitch SS-5GL monté à 45° azimut permet le recalage automatique :

1. Coupole passe à 45° → Switch activé
2. Démon détecte transition GPIO 27 (1→0)
3. Recalage automatique : `total_counts` ajusté pour afficher 45.0°
4. Dérive éliminée

### Simulation du Switch

En mode simulation, le passage par 45° est détecté automatiquement :
- Le flag `calibrated` passe à `True`
- Un callback peut être défini pour réagir à l'événement

---

## Dépannage

### Motor Service ne démarre pas

```bash
# Vérifier les logs
tail -f logs/motor_service.log

# Vérifier les permissions GPIO (production)
groups  # Doit inclure gpio, spi
```

### Encodeur non disponible

```bash
# Vérifier le démon
ps aux | grep ems22d

# Vérifier le fichier JSON
cat /dev/shm/ems22_position.json

# Relancer le démon
sudo python3 ems22d_calibrated.py
```

### Position figée en simulation

Le singleton `MovementSimulator` peut garder l'état entre les tests.
Redémarrer le Motor Service pour réinitialiser.

---

## Tests

```bash
# Tests rapides (sans dépendances lourdes)
uv run pytest tests/test_angle_utils.py tests/test_config.py tests/test_simulation.py -v

# Tests complets
uv run pytest tests/ -v

# Tests de simulation avec timing
uv run pytest tests/test_simulation.py -v
```

---

## Documentation

- **CLAUDE.md** : Guide développeur, instructions Claude Code
- **data/config.json** : Configuration complète avec commentaires
- **tests_sur_site/** : Outils de diagnostic terrain

---

## Performance

| Métrique | Valeur |
|----------|--------|
| Précision avec encodeur | ±0.3-0.5° |
| Fréquence lecture encodeur | 50 Hz |
| Latence commande web | < 100ms |
| Réduction temps moteur (adaptatif) | 85% |

---

**Version** : 4.5 Web
**Date** : Décembre 2025
**Licence** : MIT
