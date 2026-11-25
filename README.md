# IoT Watering System

Sistema de reg per a Home Assistant i AppDaemon.

## Estructura

- `*.py`: motor WateringSystem.
- [`docs/`](docs/): [arquitectura](docs/WateringSystem-Architecture.md) i [model WS Plan](docs/WS-Plan.md).
- [`yaml/automations/`](yaml/automations/): automatitzacions HA.
- [`yaml/virtual-devices/`](yaml/virtual-devices/): dispositius Virtual Components.
- [`yaml/lovelace-cards/`](yaml/lovelace-cards/): cards Lovelace.
- `tests/`: proves unitàries.

## Estat

En desenvolupament. Contracte de peticions i preflight validats; actuacions físiques desactivades. WS Scheduler inicial pendent d'adaptació al contracte actual; no desplegar encara.

## Proves

```sh
python -m unittest discover -s tests -v
```
