# Deploy-Anleitung Chat Harness

Diese Anleitung beschreibt das Aufsetzen auf einem **Contabo Cloud VPS** (oder einem ähnlichen Debian/Ubuntu-Server) mit **rootless Podman**.

## Voraussetzungen

- Debian 13 / Ubuntu 24.04 oder neuer
- Rootless Podman installiert:
  ```bash
  sudo apt update
  sudo apt install -y podman podman-compose uidmap slirp4netns
  ```
- Python 3.11+ und Node 20+
- `unprivileged_userns_clone` aktiviert (für Podman-in-Podman):
  ```bash
  sudo sysctl kernel.unprivileged_userns_clone=1
  echo "kernel.unprivileged_userns_clone=1" | sudo tee -a /etc/sysctl.conf
  ```

## Projekt klonen

```bash
cd /opt
git clone <repo-url> chat-harness
cd chat-harness
```

## Umgebung konfigurieren

Kopiere die Beispiel-`.env` und passe sie an:

```bash
cp .env.example .env
```

Wichtige Variablen für den Produktivbetrieb:

```env
DATABASE_URL=postgresql+asyncpg://chatharness:chatharness@127.0.0.1:5432/chatharness
MOCK_PODMAN=false
CHAT_CONTAINER_IMAGE=localhost/chat-harness-agent:latest
CHAT_BASE_DIR=/var/lib/chat-harness/chats
PODMAN_BINARY=podman
DEVIN_DEFAULT_MODEL=glm-5.2-high
AGY_ACP_COMMAND=npx -y agy-acp
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### API-Keys und Secrets

Für Devin (ACP/CLI):

```env
WINDSURF_API_KEY=<devin-token>
```

Für AGY und weitere ACP-Agents:

```env
AGY_API_KEY=<agy-token>
GENERIC_ACP_COMMAND=<dein-acp-server>
```

Die Werte werden von `app/services/secrets.py` gelesen und als `-e` Variablen an jeden Chat-Container übergeben.

## Setup

```bash
./scripts/setup.sh
```

Das Skript:

1. baut das Chat-Agent-Image
2. startet PostgreSQL + pgvector
3. prüft, ob `podman` verfügbar ist

## Anwendung starten

### Backend

```bash
./scripts/run-backend.sh
```

Das Backend lauscht auf `http://0.0.0.0:8000`.

### Frontend

Für Entwicklung:

```bash
./scripts/run-frontend.sh
```

Für Produktion:

```bash
cd frontend
npm install
npm run build
```

Das gebaute Frontend liegt in `frontend/dist/`.

## Reverse Proxy / TLS

Für den öffentlichen Betrieb empiehlt sich **Caddy** (einfach) oder **Nginx**:

```bash
sudo apt install -y caddy
```

`/etc/caddy/Caddyfile`:

```caddy
dein-domain.de {
  reverse_proxy /api/* 127.0.0.1:8000
  reverse_proxy /api/health 127.0.0.1:8000
  reverse_proxy 127.0.0.1:5173

  # noVNC-Popups für jeden Chat, z.B. per Port-Range
  @novnc {
    remote_ip 127.0.0.1
  }
}
```

> Hinweis: Der Frontend-Proxy muss die zufällig gemappten noVNC-Ports erreichbar machen. Die einfachste Variante ist, den Browser-Stream über den gleichen Host laufen zu lassen und über `localhost` anzusprechen.

## Chat-Container testen

```bash
./scripts/test-chat-container.sh
```

Es prüft:

- noVNC auf Port 6080
- `devin`, `agy-acp`, `playwright`
- ob rootless `podman --version` im Container klappt

## Container-Isolation und Podman-in-Podman

Jeder Chat läuft in einem eigenen rootless Podman-Container. Darin kann der Agent mit `podman build` Images bauen (Podman-in-Podman). Voraussetzungen:

- `kernel.unprivileged_userns_clone=1`
- `--security-opt seccomp=unconfined --security-opt apparmor=unconfined` (bereits im Backend gesetzt)
- Storage-Treiber im Chat-Container ist **VFS** (langsam, aber robust)

Falls verschachtelte User-Namespaces auf deinem Kernel nicht erlaubt sind, startet `podman` im Chat-Container nicht. In diesem Fall kannst du im `PodmanManager`-Befehl zusätzlich `--privileged` ergänzen (weniger isoliert, aber funktionell).

## Updates

```bash
git pull
./scripts/build-chat-image.sh
podman-compose -f infra/compose.yml up -d postgres
# Backend und Frontend neu starten
```

## Wartung

### Inaktive Chats pausieren

Das Backend prüft alle 60 Sekunden (Wert `snapshot_interval_seconds`) auf Inaktivität. Nach 30 Minuten (`inactivity_timeout_seconds`) wird der Container gestoppt, committed und als neues Image gespeichert.

### Secrets erneuern

Neue Secrets entweder in `.env` ergänzen oder in `data/secrets/secrets.enc.yaml` mit `age`/`sops` hinterlegen. `app/services/secrets.py` entschlüsselt pro Chat nur die nötigen Werte.

## Bekannte Einschränkungen

- **pgvector**: Aktuell werden Embeddings als JSON gespeichert und im Speicher durchsucht. Für große Historien empfiehlt sich eine Migration, die die `events`-Tabelle um eine `vector` Spalte erweitert.
- **VPS ohne nested virtualization**: True VMs pro Chat sind nicht möglich, deshalb rootless Podman-Container.
- **noVNC-Port**: Pro Chat-Container wird ein zufälliger Host-Port für noVNC vergeben. Für externe Zugriffe muss dieser Port erreichbar sein oder ein Reverse-Proxy muss den Browser-Stream übernehmen.
