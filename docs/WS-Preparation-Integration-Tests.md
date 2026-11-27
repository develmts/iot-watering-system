# WS Preparation — Integration tests

Data: 2026-11-27. Entorn: Home Assistant / AppDaemon, Virtual GiEX.

## Resultat

**5/5 PASS. Fita tancada en l'abast actual.**

| Test | Configuració inicial | Petició | Resultat | Temps des de PREFLIGHT_OK |
|---|---|---|---|---|
| 01 | capacity, 10 L | duration, 120 s | PREPARATION_READY | 2,042 s |
| 02 | duration, 120 s | capacity, 25 L | PREPARATION_READY | 2,045 s |
| 03 | duration, 120 s | duration, 120 s | PREPARATION_READY | 18 ms |
| 04 | capacity, 25 L | duration, 43201 s | PREPARATION_FAILED: Target outside device range | 6 ms |
| 05 | capacity, 25 L; bateria 10% | duration, 120 s | BATTERY_LOW | No arriba a Preparation |

Totes les comprovacions del runner són positives. Les dues vàlvules romanen OFF en totes les mostres. L'informe no registra errors de restauració. Els logs dels casos 01–03 confirmen PREFLIGHT_OK → PREPARATION_MODE_OK → PREPARATION_TARGET_OK → PREPARATION_READY. El cas 04 rebutja el target abans de configurar el dispositiu; el cas 05 queda denegat a Preflight.

## Implementació i reproducció

- Controller: `e0dcc6c78632559a59c474e34c1b25e617cc9bdf`.
- WateringDevice: `f4bf9b0b54912230cc8630846e9620fe5812e462`.
- Tests unitaris: `b658daf93a3d18f7f02f9074139abcf8476fe25c`.
- Runner: `b4b2a6d2875f59266acf61bc18e62d8f0b5f29f3`.

```sh
python tools/ws_preparation_runner.py --device "Virtual GiEX"
```

Informe local: `ws-preparation-report.json` (exclòs de Git). El desplegament DEV → PROD va detectar dos fitxers Python modificats en una sola recàrrega i va registrar SYSTEM_READY.

## Abast i limitacions

Preparation valida compatibilitat, configura mode abans del target, confirma els valors i avorta davant errors. Timeout de 10 s per confirmació, interval d'1 s, sense reenviaments. El dispositiu autoritzat temporalment és exclusivament Virtual GiEX, per ID. START està deshabilitat. No es persisteix encara el context d'execució.

Els timeouts i la concurrència tenen cobertura unitària, no d'integració. El test 03 no captura directament les crides de servei; el temps és coherent amb l'absència de reenviaments. El mostreig de les vàlvules no constitueix una captura contínua d'esdeveniments. No s'ha validat Preparation sobre el GiEX físic. L'informe original no s'arxiva al repositori.

## Següent fita

START sobre Virtual GiEX amb el simulador en execució. Cal definir i validar la confirmació de l'inici efectiu del reg mitjançant water_consumed (reset a zero i valor positiu), la gestió del context i els errors d'inici. No s'implementa START en aquesta fita.
