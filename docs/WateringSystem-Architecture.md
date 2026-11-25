# WateringSystem — Arquitectura i decisions de disseny

**Projecte:** IoT / Reg V3.1  
**Data de referència:** 2026-11-25  
**Estat:** decisions de disseny consolidades abans de la implementació del contracte v1.

Aquest document distingeix les decisions acordades, les limitacions temporals de la fase 1 i les qüestions pendents. No pressuposa que el codi actual ja implementi el disseny.

## 1. Objectiu i principis

Migrar progressivament la gestió del reg de les automatitzacions YAML originals a WateringSystem (WS), executat en AppDaemon, mantenint Home Assistant (HA) com a plataforma d'integració, configuració i programació.

- Separar programació, configuració, validació i execució.
- Evitar la proliferació de helpers i la duplicació de lògica.
- Mantenir el nucli del WS independent de la interfície d'usuari i dels emissors de peticions.
- Preveure l'extensibilitat sense implementar funcionalitats abans que siguin necessàries.
- Limitar la implementació de cada fase, no les possibilitats futures del contracte.

## 2. Components i responsabilitats

```text
HA helper: input_boolean.auto_watering    Virtual Device / Lovelace
                    |                              |
                    +----------+-------------------+
                               v
                         WS Scheduler (HA)
                               |
                      irrigation_request
                               |
                               v
                      WateringSystem (AppDaemon)
                               |
                  Validation / Preparation / Execution
                               |
                       HA irrigation devices
```

### 2.1. Autorització global

`input_boolean.auto_watering` es conserva com a helper estàndard de HA. És l'interruptor mestre del reg automàtic. El WS no el consulta ni necessita saber que existeix. Desactivar-lo impedeix l'emissió de peticions programades, però no prohibeix les peticions puntuals.

### 2.2. WS Scheduler

Automatització externa i nativa de HA, no un scheduler implementat dins d'AppDaemon. HA assumeix la gestió temporal i la persistència de la configuració; no es vol reproduir aquesta infraestructura dins del WS.

El Scheduler només avalua dues categories de condicions:

1. Autorització global del reg automàtic.
2. Correspondència amb el dia i l'hora programats. Enabled i temporada són validacions exclusives del WS.

Llegeix les entitats de configuració del dispositiu virtual i construeix l'esdeveniment `irrigation_request`. Envia els valors de configuració necessaris, inclosos `enabled`, `season_start` i `season_end`, sense avaluar-los. `start_time` és necessari per programar el dispar en mode scheduler, pot no existir en una configuració oneTime i mai es transmet a l'event.

No avalua bateria, pluja, humitat, disponibilitat, reg en curs ni altres restriccions operatives. Tampoc obté lectures per injectar-les a la petició.

### 2.3. WateringSystem

Rep peticions mitjançant un esdeveniment HA, no mitjançant un servei `irrigation.request`. Normalitza la petició, valida les condicions operatives, prepara els dispositius, executa el reg i informa del resultat.

Desconeix l'existència del WS Scheduler, de Virtual Components i del helper global. El contracte és l'esdeveniment, no el mecanisme d'emmagatzematge de la configuració. Qualsevol emissor compatible pot sol·licitar un reg.

## 3. Configuració i interfície: Virtual Components

### 3.1. Decisió

Utilitzar Virtual Components (HACS, `twrecked/hass-virtual`) com a mecanisme de comoditat per mantenir i modificar programacions mitjançant dispositius lògics amb entitats natives de HA. És substituïble sense modificar el WS.

Un dispositiu virtual representa una **programació**, no una vàlvula física. Una vàlvula podrà pertànyer a diverses programacions. En el futur una programació podrà incloure diverses vàlvules amb un objectiu comú.

En fase 1 cada programació apunta a una única vàlvula. No s'estableix una correspondència permanent 1:1 entre dispositius virtuals i físics.

### 3.2. Prova de concepte

S'ha provat Virtual Components v0.10.0-beta.1 amb `/homeassistant/virtual.yaml` i un dispositiu `Virtual Test` amb entitats switch, text, select, number i button. Posteriorment s'ha afegit una entitat text per a la temporada.

S'ha comprovat la creació del dispositiu i les seves entitats al registre de HA, la recàrrega de l'entrada `imported` sense reiniciar HA, la conservació dels valors modificats després de recarregar i la incorporació d'una entitat sense perdre els valors existents. La persistència després d'un reinici complet de HA encara s'ha de verificar.

L'editor extern no és necessari: es pot mantenir el YAML directament. No es compta amb atributs arbitraris personalitzats ni amb plataformes natives time/date/datetime de Virtual Components en el disseny actual. S'ha plantejat al mantenidor una consulta informativa sobre aquestes possibilitats i actualitzacions agrupades; el projecte no depèn de la seva resposta.

### 3.3. Interfície pendent

La configuració candidata inclou `enabled`, `start_time`, `watering_season`, `devices`, `target_type` i `target`. La representació definitiva del calendari, l'activació individual i els identificadors d'entitats encara no està tancada.

Es vol una mini card Lovelace tan compacta com sigui possible, amb edició còmoda. El model inicial desitjat era editar un esborrany local i confirmar amb Submit/Send, evitant escriptures immediates i helpers auxiliars. La viabilitat i implementació d'aquesta interacció estan pendents; la prova de concepte no demostra actualització atòmica de múltiples entitats.

També queda pendent resoldre el trigger temporal dinàmic, la representació futura d'una llista de dispositius i la restauració de la programació després d'un reinici.

## 4. Contracte públic: irrigation_request v1

- [Contracte scheduler](irrigation_request-scheduler.md)
- [Contracte oneTime](irrigation_request-oneTime.md)

## 5. Execució i reporting

Les restriccions operatives són responsabilitat exclusiva del WS, incloent-hi les de seguretat. WS també avalua Enabled en tots dos modes i temporada exclusivament en mode scheduler, a partir dels valors rebuts. El Reporter informa del motiu de rebuig. Un diccionari `validators` buit no desactiva les validacions obligatòries.

La preparació de la vàlvula no és una condició de preflight: el WS ha de configurar el mode corresponent, verificar que ha estat acceptat, configurar l'objectiu i verificar-lo abans de START. Si la preparació falla, no s'ha d'iniciar el reg. Es manté el principi de rebutjar una petició si el dispositiu ja està regant.

Per al GX02 i el reg temporitzat, la vàlvula gestiona la finalització del seu propi cicle; no s'ha de substituir per un OFF temporitzat ordinari des de HA. La migració de la gestió STOP a AppDaemon continua pendent.

Es conserva el Reporter existent: logging i notificacions persistents associades al `tag` quan es proporciona. El tag constant dels exemples és provisional; queda pendent determinar la política d'identificació de cicles i evitar acumulacions indesitjades.

## 6. Issue tècnica ajornada: Extensible Reading & Validation Architecture

**Estat:** disseny conceptual acordat, implementació ajornada. Encara no es disposa dels sensors d'humitat.

### 6.1. Obtenció de lectures (Pull)

El WS obté els valors des de HA quan els necessita. L'emissor pot especificar en el futur quines fonts i validacions addicionals corresponen a la petició, però no injecta valors mesurats ni pot eludir les restriccions obligatòries.

`readings` del contracte públic es reserva per descriure fonts, no per transportar valors. `validators` es reserva per indicar validacions addicionals. La sintaxi interna de tots dos diccionaris queda oberta. Els perfils de validació o zones són alternatives discutides, no camps addicionals acordats.

Separar les dades obtingudes internament de la petició original. El futur ReadingProvider/Reading Engine recopilarà i normalitzarà les lectures necessàries, preferentment on demand aprofitant els estats de HA disponibles a AppDaemon. Llegir un estat no força una mesura física nova.

Els validators treballaran sobre una instantània de lectures, no aniran individualment a consultar HA. La instantània ha de poder representar valors individuals, múltiples i derivats, amb informació de disponibilitat, unitats i vigència quan sigui possible.

### 6.2. Validació modular

Motor independent del nucli amb una interfície comuna, configuració declarativa YAML, resultats normalitzats i integració amb el Reporter. Preferència per validators genèrics reutilitzables i càrrega dinàmica de nous tipus.

Exemples conceptuals (noms i sintaxi no definitius): `numeric_threshold`, `state_match`, `elapsed_time`, `availability`. Els casos especials podran requerir un mòdul Python propi.

- Nova regla o canvi de sensor/llindar: configuració.
- Nou tipus de validator: mòdul Python, sense modificar el motor si la interfície ho permet.
- Nova capacitat estructural: modificació del nucli quan sigui necessària.

Preveure àmbits globals, per dispositiu i per zona. No construir un llenguatge de regles universal.

### 6.3. Casos pendents d'estudi

**Pluja en les últimes 24 hores.** Un detector binari només indica pluja sí/no. Cal obtenir informació històrica per saber si ha plogut, durant quant de temps o quan ha deixat de ploure. No permet calcular volum de precipitació. Preferència inicial per sensors derivats de HA quan sigui viable; un History Reader és una alternativa, no una implementació decidida.

**Múltiples sensors d'humitat.** Una zona pot tenir diverses lectures. L'obtenció ha de preservar els valors originals; la política de validació decidirà com combinar-los (mínim, màxim, mitjana, mediana, majoria, etc.). No s'ha escollit cap agregació.

**Qualitat de les lectures.** Cal definir polítiques per a dades absents, no disponibles, antigues o contradictòries, i antiguitat admissible per font. `last_changed`, `last_updated` i l'instant de mesura física no són equivalents. No s'han acordat llindars de vigència.

**Multidispositiu.** Queda pendent decidir execució simultània o seqüencial i tractament de validacions parcialment superades.

### 6.4. Límit d'abast

Preveure les interfícies sense construir ara dos motors extensibles complets. Implementar només les capacitats necessàries quan apareguin necessitats reals. La fase 1 no inclou el ReadingProvider, el motor modular de validators ni les noves restriccions ambientals.

## 7. Estat de partida i verificació

Després de la migració a HAOS 18.4 i HA Core 2026.11.3, AppDaemon (add-on 0.19.2) ha recuperat la connexió amb HA i ha inicialitzat `watering_system`. S'ha verificat el circuit HA event → AppDaemon → Reporter → notificació persistent amb una petició deliberadament invàlida (`mode: validation`, `tag: ws_post_migration_test`). La prova no ha activat el reg físic.

El codi existent encara utilitza `mode` i necessita adaptar-se al contracte acordat. El scheduler antic es manté durant la migració; amb `auto_watering` desactivat no ha d'iniciar el reg. Cal evitar que els dos schedulers emetin peticions de reg en producció durant la transició.

## 8. Full de ruta immediat

Ordre acordat: primer el contracte, després la configuració i interfície.

1. Revisar el codi actual abans de modificar-lo.
2. Implementar la normalització i validació del contracte v1 i adaptar la preparació/execució als objectius.
3. Verificar les peticions vàlides i invàlides, inicialment sense activar físicament el reg; registrar la petició original per facilitar les proves.
4. Definir el dispositiu virtual definitiu i la mini card; verificar persistència després de reiniciar HA.
5. Implementar WS Scheduler perquè llegeixi la configuració i emeti `irrigation_request`.
6. Validar el circuit complet i planificar la substitució segura de l'automatització antiga.

Les dues línies (contracte i interfície) poden avançar independentment un cop definit el contracte. No s'inclouen en aquesta fase ni el suport multidispositiu efectiu ni la issue de lectures i validators.

## 9. Nice to have @ V2: HA Action facade

**Estat:** millora opcional ajornada a V2; no és un requisit de la fase actual.

Estudiar una Action nativa de HA, `irrigation.request`, com a façana que emeti l'esdeveniment `irrigation_request` amb el contracte corresponent. Aportaria autocompleció, descobriment, documentació dels camps, selectors i una interfície gràfica per a peticions manuals.

Es mantindria el bus d'esdeveniments com a contracte del WS i la validació definitiva dins d'AppDaemon. La façana seria opcional i no substituiria l'accés directe mitjançant l'esdeveniment. Caldrà valorar si compensa mantenir una petita integració pròpia de HA. No s'acorda ara cap implementació ni es modifica el contracte actual.

---

Document de decisions, no especificació exhaustiva del codi existent. Les sintaxis futures i les polítiques marcades com a pendents no s'han de considerar aprovades ni implementades.
