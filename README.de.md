# Dropper

_Die Neuauflage von TwitchCPM._ · [English](README.md) · [Live-Demo](https://mki002.github.io/dropper-app/demo/)

Farmt Twitch-Drops automatisch in einem Docker-Container: findet selbst Channels, die gerade Drops aktiv haben, schaut sie im Hintergrund (ohne Video herunterzuladen) und holt fertige Drops zuverlässig ab. Alles wird über ein WebUI gesteuert, eine Config-Datei muss nicht mehr bearbeitet werden.

## Was es kann

- **Automatische Channel-Suche:** kennt alle laufenden Drop-Kampagnen (siehe [Woher die Kampagnen kommen](#woher-die-kampagnen-kommen)), durchsucht pro Spiel das Twitch-Verzeichnis nach Streams mit aktivierten Drops und fragt bei jedem Channel nach, welche Kampagnen dort *tatsächlich gerade* laufen. Kampagnen mit festen Channel-Listen werden direkt über diese Channels abgearbeitet.
- **Neue Channels dynamisch:** bei jedem Neuladen (Standard alle 30 Minuten und genau zum Start/Ende einer Kampagne) werden neue Channels und neue Kampagnen automatisch übernommen. Geht ein Stream offline, wechselt das Spiel oder kommt kein Fortschritt mehr, wird sofort auf den nächsten passenden Channel gewechselt.
- **Zuverlässiges Claimen:** alles, was abgeholt werden kann, wird automatisch abgeholt (abschaltbar), über mehrere unabhängige Wege, siehe unten.
- **WebUI** auf Port 8080, schlicht und dunkel, in 12 Sprachen (Englisch als Standard, außerdem Deutsch, Spanisch, Französisch, Italienisch, Portugiesisch, Polnisch, Türkisch, Russisch, Japanisch, Koreanisch, Chinesisch), auch am Handy bedienbar:
  - *Übersicht:* was gerade geschaut wird und warum genau dieser Channel, Fortschritt des aktuellen Drops, Warteschlange, zuletzt geholte Drops.
  - *Drops:* jeder einzelne Drop mit Status (bereit, fehlgeschlagen, läuft, abgeholt, gesperrt, demnächst, beendet), Fortschritt und Abholen-Knopf; bei Fehlern der Grund, ein Link zum Verknüpfen und ein neuer Versuch. Dazu der komplette Claim-Verlauf und die Sammlung aller Belohnungen.
  - *Kampagnen:* alle Kampagnen mit Filter nach Spiel, Status, Belohnungsart (Item/Badge/Emote) und verknüpftem Account. Pro Kampagne ein Schalter zum An-/Abschalten, pro Spiel „Priorisieren" und „Ausschließen", und der Grund, warum eine Kampagne gerade übersprungen wird.
  - *Channels:* alle gefundenen Live-Channels mit ihren Drop-Kampagnen; manuell schauen, bevorzugen oder sperren.
  - *Statistiken:* Watchtime pro Tag, pro Spiel und pro Channel, Claims inklusive fehlgeschlagener Versuche, Kanalpunkte.
  - *Einstellungen:* alles, was früher in der Config stand, wirkt sofort ohne Neustart. Die Prioritätsliste nimmt jedes Spiel auf, auch eins ohne laufende Kampagne ([Spiele beobachten](#spiele-beobachten)), lässt sich per Pfeil sortieren und zeigt pro Spiel den Stand; „Priorisieren“ auf einer Kampagne setzt das Spiel ganz nach oben. Dazu die Benachrichtigungen.
  - *Log:* Live-Log mit Filter.
  - `Strg+K` öffnet die Schnellaktionen, `1` bis `7` wechseln die Seiten.
- **Extras:** Kanalpunkte-Bonus automatisch abholen, [Discord-/Webhook-Benachrichtigungen](#benachrichtigungen) mit wählbaren Ereignissen, optionaler Passwortschutz fürs WebUI, Proxy-Unterstützung.

## Start

```bash
git clone https://github.com/MKI002/dropper-app.git
cd dropper-app
docker compose up -d --build
```

Dann `http://<server>:8080` öffnen. Beim ersten Start zeigt Dropper einen 8-stelligen Code. Diesen auf <https://www.twitch.tv/activate> eingeben, fertig. Die Anmeldung wird in `./data/auth.json` gespeichert und überlebt Neustarts.

Ohne Compose:

```bash
docker build -t dropper .
docker run -d --name Dropper -p 8080:8080 -v $(pwd)/data:/data --restart unless-stopped dropper
```

Fertige Images (amd64 und arm64) baut eine GitHub Action bei jedem Push auf `main` nach `ghcr.io/mki002/dropper-app:latest`.

### Unraid

1. *Docker → Add Container* öffnen.
2. Ausfüllen:
   - **Name:** `Dropper`
   - **Repository:** `ghcr.io/mki002/dropper-app:latest`
   - **WebUI** (unter *Show more settings*): `http://[IP]:[PORT:8080]/`
   - **Icon URL:** `https://raw.githubusercontent.com/MKI002/dropper-app/main/unraid/icon.png`
3. Unten über *Add another Path, Port, Variable…* hinzufügen:
   - **Port:** Container-Port `8080`, Host-Port `8080`
   - **Path:** Container-Pfad `/data`, Host-Pfad `/mnt/user/appdata/dropper`
   - **Variable** `PUID` = `99` und **Variable** `PGID` = `100`
   - optional **Variable** `WEBUI_PASSWORD`
4. *Apply*, dann im Docker-Tab auf das Icon → *WebUI* und den Login-Code auf twitch.tv/activate eingeben.

Schneller mit Template: [`unraid/dropper.xml`](unraid/dropper.xml) nach `\\<server>\flash\config\plugins\dockerMan\templates-user\` kopieren (Flash-Freigabe). Danach steht *Dropper* bei *Add Container* im Feld *Template* und alles ist vorausgefüllt.

### Umstieg von PurpleRain

Dropper ist der neue Name von PurpleRain. Login, Einstellungen und Statistik bleiben erhalten:

- **Unraid:** den bestehenden Container bearbeiten, bei **Repository** `ghcr.io/mki002/dropper-app:latest` eintragen und *Apply*. Den Pfad `/mnt/user/appdata/purplerain` einfach lassen (den Container in `Dropper` umzubenennen ist optional). Alternativ den alten Container stoppen, den Ordner nach `/mnt/user/appdata/dropper` verschieben und Dropper über das Template anlegen.
- **Compose / docker run:** das Image auf `ghcr.io/mki002/dropper-app:latest` ändern, das `/data`-Volume bleibt.
- Die alten Variablen `PURPLERAIN_DATA` und `PURPLERAIN_PROXY` funktionieren weiter, die neuen heißen `DROPPER_DATA` und `DROPPER_PROXY`.

### Rechte

Der Container startet als root, gibt `/data` an `PUID:PGID` (Standard 1000:1000, Unraid 99:100) und läuft dann als dieser User.

### Umgebungsvariablen

| Variable | Standard | Zweck |
|---|---|---|
| `WEBUI_PASSWORD` | leer | Wenn gesetzt, ist das WebUI per Basic Auth geschützt |
| `WEBUI_USER` | `admin` | Benutzername dazu |
| `PORT` | `8080` | Port des WebUI |
| `LOG_LEVEL` | `INFO` | `DEBUG` für Fehlersuche |
| `TZ` | – | Zeitzone für die Logs |
| `PUID` / `PGID` | `1000` | User/Gruppe für die Dateien in `/data` (Unraid: `99`/`100`) |

Alles andere stellst du im WebUI ein. Die Werte liegen in `data/settings.json`, die Statistik in `data/stats.db` (SQLite).

## Warum das Claimen jetzt zuverlässig ist

Der häufigste Grund für verpasste Drops ist, dass ein Miner sich auf ein einziges Echtzeit-Event („Drop fertig") verlässt. Geht das Event verloren oder schlägt der eine Claim-Aufruf fehl, bleibt der Drop liegen. Dropper hat deshalb vier unabhängige Wege:

1. **Echtzeit (PubSub):** Twitch meldet „Drop fertig" mit Claim-ID, der Drop wird sofort geholt.
2. **Fortschritts-Abfrage:** jede Minute wird der aktuelle Drop-Fortschritt per API abgefragt; sobald die Minuten erreicht sind, wird geclaimt, auch ohne Echtzeit-Event.
3. **Inventar-Check (Standard alle 5 Minuten):** das komplette Inventar wird gelesen und *jeder* fertige, aber nicht geholte Drop geclaimt, auch solche aus beendeten Kampagnen (bis 24 h danach) oder von anderen Geräten.
4. **Retry mit Fallback-ID:** jeder Claim wird mit Backoff wiederholt. Ist die gemeldete Claim-ID ungültig, wird die aus User-, Kampagnen- und Drop-ID gebildete ID versucht. Fehlversuche landen in der Statistik und werden beim nächsten Inventar-Check erneut probiert.

Ein vollständig geschauter, aber nicht geholter Drop gilt außerdem nicht mehr als „farmbar", damit nicht weiter sinnlos derselbe Channel geschaut wird.

Lehnt Twitch das Abholen ab (typisch: Ingame-Item, aber der Spiel-Account ist nicht verknüpft), zeigt der Drops-Reiter beim Drop den Grund, einen Link zum Verknüpfen und einen Knopf für einen neuen Versuch. Automatisch wird es nach 5, 10, 20, 40 und danach alle 60 Minuten erneut probiert, nach dem Verknüpfen sofort. Wer selbst abholen will, schaltet *Einstellungen → Fertige Drops automatisch abholen* aus.

## Benachrichtigungen

Unter *Einstellungen → Benachrichtigungen* die Webhook-URL eintragen (in Discord: *Servereinstellungen → Integrationen → Webhooks → Webhook-URL kopieren*) und auswählen, worüber Dropper berichtet:

- **Drop abgeholt**, mit Belohnung, Bild und Stand der Kampagne
- **Abholen fehlgeschlagen**, einmal pro Drop, mit dem Grund von Twitch
- **Kampagne abgeschlossen**, wenn alle Drops einer Kampagne geholt sind
- **Drops für ein beobachtetes Spiel**, sobald ein Spiel von deiner Prioritätsliste eine Kampagne bekommt, auch schon bevor sie startet, mit Hinweis, falls der Spiel-Account noch verknüpft werden muss
- **Neue Kampagne**, wenn eine gewünschte Kampagne gerade begonnen hat (standardmäßig aus)
- **Login nötig**, wenn die Twitch-Anmeldung abgelaufen ist und das Farmen wartet

Bei einer Discord-URL lassen sich darunter auch **Name** und **Profilbild** des Absenders einstellen. Ohne eigene Angaben schreibt Dropper als „Dropper“ mit seinem Icon. Weil Discord Profilbilder nur von öffentlich erreichbaren Adressen lädt, macht Dropper ein hochgeladenes Bild zum Bild des Webhooks. Ein Bild, das du in Discord selbst beim Webhook eingestellt hast, bleibt so lange, bis du in Dropper eins hochlädst.

*Testnachricht senden* probiert URL, Name und Bild sofort aus, auch vor dem Speichern. Was kurz nacheinander passiert, kommt gebündelt in einer Nachricht, in der Sprache des WebUI. Andere URLs als Discord bekommen JSON mit `event`, `text` und den Details. Die URL ist ein Schlüssel zum Channel und liegt nur in `data/settings.json`.

## Spiele beobachten

Auf die Prioritätsliste (*Einstellungen → Prioritätsliste*) kommt jedes Spiel, auch eins, das gerade keine Drops hat, zum Beispiel Minecraft oder Sea of Thieves. Beim Tippen schlägt Dropper Spiele aus laufenden Kampagnen und aus deinem Verlauf vor und sucht den Namen bei Twitch, damit die Schreibweise stimmt und das Cover angezeigt wird. Groß-/Kleinschreibung, Akzente und Bindestriche spielen beim Abgleich keine Rolle.

Jede Zeile zeigt den Stand: wird gefarmt, Platz in der Warteschlange, Kampagne startet am …, wartet auf eine Kampagne, oder *Nicht auf Twitch gefunden*, wenn es kein Spiel mit diesem Namen gibt. Spiele ohne Kampagne stehen auch im Kampagnen-Reiter unter „Wartet auf Drops“.

Bei jedem Neuladen sucht Dropper für diese Spiele zusätzlich nach Streams mit aktivierten Drops. So fällt eine neue Kampagne auf, sobald die ersten Channels sie anbieten, auch wenn der Katalog sie noch nicht kennt. Gefarmt wird sie dann in der Reihenfolge der Liste, und auf Wunsch kommt eine Benachrichtigung.

## Woher die Kampagnen kommen

Seit September 2026 liefert Twitch die vollständige Kampagnenliste (und die Kampagnen-Details) nicht mehr an Apps aus, sondern nur noch an den Browser mit einer Integritätsprüfung. Ein Miner sieht dann nur noch die Kampagnen, die er schon angefangen hat. Dropper gleicht das so aus:

1. **Katalog:** Die Liste der laufenden und kommenden Kampagnen kommt aus dem öffentlichen Katalog von [ttvdrops](https://ttvdrops.lovinator.space/) (offene Daten, CC0).
2. **Drops pro Channel:** Für Spiele aus dem Katalog sucht Dropper Live-Channels und fragt bei Twitch nach, welche Drops dort gerade laufen. Das funktioniert weiterhin und liefert die Belohnungen, Minuten und Zeitfenster.
3. **Inventar:** Dein Fortschritt kommt wie bisher aus deinem Twitch-Inventar.

Ob ein Spiel-Account verknüpft ist, verrät Twitch für solche Kampagnen nicht. Dropper nimmt dann an, dass er verknüpft ist, und markiert die Kampagne mit „Verknüpfung unbekannt". Liefert Twitch die Liste wieder normal, wird automatisch wieder sie benutzt. Der Katalog lässt sich unter *Einstellungen → Erweitert → Kampagnen-Katalog* ändern oder mit einem leeren Feld abschalten.

## Auswahl-Logik

1. Kampagnen werden gefiltert: deaktivierte Kampagnen, ausgeschlossene Spiele, Whitelist-Modus, und Ingame-Items ohne verknüpften Spiel-Account fallen raus (abschaltbar). Badges und Emotes brauchen keine Verknüpfung.
2. Sortierung: zuerst deine Prioritätsliste, danach entweder „endet zuerst" oder „am knappsten" (verbleibende Zeit geteilt durch benötigte Minuten).
3. Für die erste Kampagne mit einem passenden Live-Channel wird geschaut. Reihenfolge der Channels: bevorzugte Channels, dann Channels aus der Kampagnen-Liste, dann nach Zuschauern. Läuft der aktuelle Channel noch für diese Kampagne, wird nicht unnötig gewechselt.
4. Kommt 12 Minuten lang kein Fortschritt, wird der Channel 30 Minuten pausiert und der nächste genommen.

Die Übersicht zeigt unter dem aktuellen Channel, warum gerade er läuft (Platz der Kampagne in der Warteschlange, wie viele Live-Channels sie anbieten und nach welcher Regel gewählt wurde). Im Channels-Reiter steht pro Channel, welche Kampagnen Twitch dort meldet und warum nicht gewünschte übersprungen werden.

## Wenn Twitch etwas ändert

Twitch identifiziert API-Abfragen über Hashes, die sich gelegentlich ändern. Für die wichtigsten Abfragen kennt Dropper mehrere Hashes und wechselt bei `PersistedQueryNotFound` automatisch auf den nächsten. Falls trotzdem eine Abfrage mit `PersistedQueryNotFound` scheitert, kann der neue Hash unter *Einstellungen → Erweitert → GQL-Hash-Overrides* eingetragen werden, ohne neues Image. Die Standardwerte stehen in [`dropper/constants.py`](dropper/constants.py).

## Entwicklung

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
DROPPER_DATA=./data python -m dropper
```

Die API-Doku gibt es unter `/api/docs`.

Aufbau:

| Datei | Inhalt |
|---|---|
| `dropper/twitch.py` | HTTP, Device-Code-Login, GQL mit Retry und Rate-Limit |
| `dropper/catalog.py` | Öffentlicher Kampagnen-Katalog als Ersatz für die gesperrte Twitch-Liste |
| `dropper/models.py` | Kampagnen, Drops, Channels |
| `dropper/selection.py` | Filter und Channel-Auswahl (ohne I/O, getestet) |
| `dropper/miner.py` | Ablauf: Laden, Suchen, Schauen, Claimen |
| `dropper/pubsub.py` | Echtzeit-Events |
| `dropper/stats.py` | SQLite-Statistik |
| `dropper/web.py` | REST-API |
| `dropper/static/` | WebUI ohne Build-Schritt: `js/app.js` (Seiten), `js/i18n.js` (Sprachen), `js/fx.js` (Effekte), `css/app.css`, `locales/*.json` |

Neue Texte kommen zuerst nach `locales/en.json` und dann in alle anderen Sprachdateien; `tests/test_locales.py` prüft, dass keine Übersetzung fehlt und Platzhalter und Pluralformen stimmen.

Die Twitch-Anbindung (Login per Android-TV-Client, Watch-Events, GQL-Operationen) orientiert sich am Vorgehen von [TwitchDropsMiner](https://github.com/DevilXD/TwitchDropsMiner) und [Twitch-Channel-Points-Miner](https://github.com/0x8fv/Twitch-Channel-Points-Miner).
