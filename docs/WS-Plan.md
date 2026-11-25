# WS Plan — model de dispositiu virtual v1

Data: 2026-11-25. Complement de [WateringSystem-Architecture.md](WateringSystem-Architecture.md).

## Responsabilitats

El WS Plan és la configuració persistent d'un pla de reg, representada com un dispositiu de Virtual Components (0.10.0-beta.1). El nom de cada instància és lliure i no té semàntica per al sistema. Un pla pot referenciar diversos dispositius físics en el futur; la fase 1 només n'admet un per petició.

WS Scheduler consumeix la configuració i decideix quan emetre irrigation_request. L'autorització global input_boolean.auto_watering és independent del pla. Enabled activa individualment el pla. WateringSystem valida la petició i les condicions operatives; WateringDevice encapsula les particularitats físiques. WateringSystem no depèn de Virtual Components.

## Entitats

| Nom | Plataforma | Valor de referència | Semàntica |
|---|---|---|---|
| Enabled | switch | off | Activació individual |
| Start Time | text | 09:00 | Hora local HH:MM |
| Season Start | text | 04-01 | Inici anual MM-DD |
| Season End | text | 10-31 | Final anual MM-DD |
| Devices | text | ["Watering Control a4f9"] | Array JSON de noms de dispositius HA |
| Target Type | select | duration | duration o capacity |
| Target | number | 600 | Segons enters o litres segons Target Type |

Totes les entitats són persistents. Les dates són inclusives, sense any; el Scheduler haurà de validar dates reals i gestionar intervals que travessin el canvi d'any. Devices té un màxim de 255 caràcters, límit de l'estat HA. La fase 1 exigeix exactament un nom de dispositiu. Target té límits provisionals d'edició 1–3600, sense unitat fixa; no són límits físics. El contracte continua admetent capacitats decimals. El Scheduler haurà de convertir el target de durada a enter sense truncar silenciosament valors fraccionaris.

## YAML de referència

Exemple de fitxer virtual.yaml. En un fitxer existent, afegir només el dispositiu dins de devices. El nom i els valors són exemples, no convencions obligatòries.

```yaml
version: 1
devices:
  WS Plan Example:
    - platform: switch
      name: Enabled
      initial_value: "off"
      persistent: true
    - platform: text
      name: Start Time
      initial_value: "09:00"
      min: 5
      max: 5
      pattern: '^([01][0-9]|2[0-3]):[0-5][0-9]$'
      persistent: true
    - platform: text
      name: Season Start
      initial_value: "04-01"
      min: 5
      max: 5
      pattern: '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
      persistent: true
    - platform: text
      name: Season End
      initial_value: "10-31"
      min: 5
      max: 5
      pattern: '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
      persistent: true
    - platform: text
      name: Devices
      initial_value: '["Watering Control a4f9"]'
      min: 2
      max: 255
      persistent: true
    - platform: select
      name: Target Type
      options:
        - duration
        - capacity
      initial_value: duration
      persistent: true
    - platform: number
      name: Target
      initial_value: "600"
      min: 1
      max: 3600
      persistent: true
```

## Limitacions i evolució

- Virtual Components no ofereix plataformes date/time/datetime en la versió estudiada. La UI futura pot editar les entitats text mitjançant controls especialitzats.
- Number no admet el paràmetre step en 0.10.0-beta.1: comprovat amb step 0.1 i 1; el codi font confirma que min/max admeten float però step no forma part de l'esquema.
- Les expressions regulars només validen el format, no totes les dates possibles.
- Readings i Validators no es representen encara al pla. El Scheduler enviarà diccionaris buits en fase 1. El mecanisme futur d'emmagatzematge queda obert; 255 caràcters poden ser insuficients.
- Descobriment i normalització de capacitats dels dispositius, opcions dinàmiques de Target Type i límits dependents del dispositiu: ajornats. No codificar particularitats del GiEX al model genèric.
- Card funcional primer; card presentable i edició amb Submit després, si és viable.

## Estat de verificació

Creació de les set entitats comprovada mitjançant Reload de Virtual Components amb Target min 1, max 3600 i sense step. La configuració de referència no implica que el Scheduler o la card estiguin implementats. Les actuacions físiques de WateringSystem continuen desactivades.
