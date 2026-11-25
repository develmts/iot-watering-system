# irrigation_request v1 — oneTime

**Revisió acordada el 2026-11-25:** Enabled i temporada es validen a WS; el Scheduler només programa i autoritza l'emissió. Aquesta revisió està pendent d'implementació al codi.

## 1. Exemple

```yaml
event: irrigation_request
event_data:
  version: 1
  request_mode: oneTime
  devices:
    - "Watering Control a4f9"
  target_type: duration
  target: 600
  enabled: true
  readings: {}
  validators: {}
  tag: ws_manual
```

El nom del dispositiu i el tag de l'exemple són il·lustratius; no constitueixen una configuració definitiva.

## 2. Camps

| Camp | Tipus | Obligatori | Semàntica / restriccions de fase 1 |
|---|---|---|---|
| `version` | Integer | No | Enter positiu; default `1`. No es restringeix a `1`. |
| `request_mode` | String | Sí | `oneTime`. |
| `devices` | List[String] | Sí | Llista de noms de dispositius. Exactament un element en fase 1. |
| `target_type` | String | Sí | `duration` o `capacity`. |
| `target` | Number | Sí | Positiu; enter en segons per a duration, numèric en litres per a capacity. |
| `readings` | Dictionary | No | Default `{}`; només buit en fase 1. |
| `validators` | Dictionary | No | Default `{}`; només buit en fase 1. |
| `tag` | String | Sí | Identificador associat al reporting, obligatori en tots dos modes. |
| `enabled` | Boolean | Sí | Autorització individual, obligatòria i avaluada en tots dos modes. |
| `season_start` | Qualsevol | No | Ignorat completament si és present. |
| `season_end` | Qualsevol | No | Ignorat completament si és present. |

## 3. Evolució i normalització

- `request_mode` substitueix l'antic `mode`.
- S'incorporen `target_type`, `target` i `version`.
- Es conserva `devices` com a llista, encara que només s'admeti un element temporalment. Una petició múltiple es rebutja explícitament en fase 1; no s'ignoren elements.
- `tag` passa a ser obligatori en tots dos modes.
- `enabled` és obligatori en tots dos modes; false impedeix l'execució.
- En mode `oneTime`, els camps de temporada s'ignoren completament si són presents: sense validació de format, error ni WARNING; es conserven només a la petició original registrada per `REQUEST_RECEIVED`, no a la normalitzada.
- Les restriccions operatives i de seguretat s'apliquen en tots dos modes. La configuració rebuda no constitueix lectures operatives.
- `readings` i `validators` es reserven com a diccionaris buits. Es rebutgen continguts no buits durant la fase 1.
- El versionat permetrà seleccionar mecanismes de normalització quan hi hagi versions diferents. Ara només es valida que sigui un enter positiu; no s'implementa dispatch per versions ni una política de compatibilitat futura. Això implica que un número superior a 1 no garanteix suport semàntic d'una versió futura.
- No es decideix encara si s'ha de mantenir compatibilitat temporal amb l'antic camp `mode`.

### 3.1. Camps desconeguts

Política permissiva amb advertència: `REQUEST_RECEIVED` conserva íntegrament les dades originals abans de qualsevol validació. Els camps desconeguts generen un `WARNING` amb codi `UNKNOWN_REQUEST_FIELDS` i els noms dels camps, sense notificació persistent. Es descarten de la petició normalitzada. `metadata` d'AppDaemon queda exempta de l'advertència. Les validacions obligatòries no canvien; un camp desconegut no garanteix que la seva semàntica sigui respectada.

## 4. Identificació i objectius

Es manté la identificació mitjançant `friendly_name`, resolt pel WS a `device_id`. La resolució ha de ser inequívoca: si no existeix o hi ha ambigüitat, es rebutja la petició.

L'objectiu és comú a tots els dispositius d'una petició. Objectius diferents impliquen peticions independents. Les unitats del contracte són independents de les unitats internes de cada vàlvula. WS farà la conversió quan sigui possible; si la unitat no es pot determinar o el tipus no és compatible, es rebutja el reg, sense assumir unitats.


`start_time` no forma part de l'event. Vegeu [l'arquitectura](WateringSystem-Architecture.md).
