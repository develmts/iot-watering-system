# WS oneTime

Script natiu de Home Assistant per sol·licitar un reg manual a WateringSystem V3.

## Configuració actual (2026-11-26)

- Nom oficial: WS oneTime.
- Event: `irrigation_request`, version 1, request_mode: oneTime.
- Dispositiu real: Watering Control a4f9.
- Objectiu: duration, 600 segons.
- Tag: ws_manual_nw.
- `enabled: false` provisionalment, per protegir la vàlvula real.

El script emet l'event, però WateringSystem denega la petició amb REQUEST_DISABLED abans de resoldre el dispositiu. No depèn de l'autorització global auto_watering ni de la temporada. Les validacions operatives continuen sent obligatòries quan s'habiliti.

## Instal·lació i ús futur

El YAML de referència és [WS-oneTime.yaml](../yaml/scripts/WS-oneTime.yaml).

Durant la migració final, el botó Lovelace existent conservarà el diàleg de confirmació i substituirà la seva acció actual per una crida al nou script:

```yaml
tap_action:
  action: perform-action
  perform_action: script.ws_onetime
  confirmation:
    text: "Are you sure you want to start watering?"
```

L'identificador del script és orientatiu: verificar l'entity_id real a Home Assistant abans de configurar el botó.

No canviar enabled a true ni substituir l'acció del botó existent fins que es decideixi habilitar el reg manual V3. L'execució física de WateringSystem encara està deshabilitada en la fase actual.

La còpia del repositori es basa en el YAML acordat i el canvi de nom i enabled comunicats per l'usuari; no és una exportació directa de Home Assistant.
