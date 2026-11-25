# WS Scheduler — programació temporal

Validació experimental: 2026-11-25, HA Core 2026.11.3.

## Disseny

El dispositiu virtual és la font de configuració. Un template sensor basat en triggers converteix el text HH:MM en el timestamp de la pròxima ocurrència. El Scheduler utilitza un trigger time natiu. No hi ha polling cada minut, helpers editables addicionals ni automatització auxiliar. El sensor es reprograma independentment del Scheduler i de l'autorització de reg, mitjançant el seu propi timestamp amb offset de 10 segons.

## Reproducció

- [Template sensor](../yaml/templates/WS-Plan-Next-Run.yaml): incorporar el bloc a templates.yaml, inclòs amb `template: !include templates.yaml` a configuration.yaml. No duplicar la clau template.
- [Automatització de prova](../yaml/automations/WS-Scheduler-Test.yaml): només crea una notificació persistent; no emet peticions de reg.
- Els identificadors NW corresponen a la configuració de laboratori, no a una convenció arquitectònica.
- Comprovar configuració, recarregar templates, activar l'automatització de prova i modificar Start Time a una hora futura propera. Comprovar notificació i timestamp del dia següent després de 10 segons.

## Evidència

| Prova | Resultat |
|---|---|
| Start Time 20:00 | PASS: 2026-11-25T19:00:00+00:00 |
| Canvi a 08:00 ja passat | PASS: 2026-11-26T07:00:00+00:00 |
| Trigger temporal | PASS: notificació WS Scheduler Test / Scheduled trigger executed successfully. |
| Autoreprogramació | PASS: usuari confirma notificació i reprogramació correctes a les 19:22 hora local |
| Reinici HA | Pendent |
| Start Time 00:00 | Pendent |

Primer intent d'autoreprogramació no concloent: notificació correcta però timestamp no avançat; possible càrrega incorrecta de templates.yaml, causa no confirmada. Repetició satisfactòria sense canvis de disseny. No es disposa del timestamp exacte de la darrera repetició.

## Límits i pendents

Verificar restauració del text i ordre d'arrencada, execució a mitjanit, recàrrega de templates sense canvi d'estat i transicions horàries DST. Un reinici o recàrrega durant els 10 segons entre execució i reprogramació pot requerir recuperació; no validat. No es defineix recuperació d'execucions perdudes durant una aturada.

El Scheduler definitiu encara no està implementat. Llegirà la configuració actual quan es dispari, comprovarà l'autorització global i emetrà la petició. WS valida enabled, temporada i condicions operatives.
