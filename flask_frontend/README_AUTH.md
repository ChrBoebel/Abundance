# Flask Frontend - Passwort-Authentifizierung

## Übersicht

Das Flask-Frontend ist mit einer einfachen Passwort-only Authentifizierung geschützt. Kein Username erforderlich, keine Datenbank nötig.

## Environment Variables

### Erforderliche Variablen

Setze diese Variablen in deiner `.env` Datei oder in Railway:

```bash
# Flask Session Secret (WICHTIG: Niemals committen!)
SECRET_KEY=dein-zufälliger-secret-key

# App-Passwort für Login
APP_PASSWORD=dein-gewähltes-passwort
```

### Secret Key generieren

Generiere einen sicheren Random-Key mit Python:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Beispiel-Ausgabe: `a4f7d9c2b1e8f3a6d5c9b2e1f4a7d8c3b6e9f2a5d8c1b4e7f0a3d6c9b2e5f8a1`

## Lokale Entwicklung

1. **Dependencies installieren:**
   ```bash
   cd flask_frontend
   pip install -r requirements.txt
   ```

2. **`.env` Datei erstellen:**
   ```bash
   cp ../.env.example ../.env
   # Dann editiere .env und setze SECRET_KEY und APP_PASSWORD
   ```

3. **Server starten:**
   ```bash
   python app.py
   ```

4. **Im Browser öffnen:**
   ```
   http://localhost:4290
   ```

5. **Login:**
   - Passwort eingeben (das in `APP_PASSWORD` gesetzt wurde)
   - Session bleibt aktiv bis Browser geschlossen wird

## Railway Deployment

### Environment Variables setzen:

In Railway Dashboard → Service → Variables:

```
SECRET_KEY=<generierter-key-aus-python-secrets>
APP_PASSWORD=<dein-passwort>
GOOGLE_API_KEY=<dein-google-key>
TAVILY_API_KEY=<dein-tavily-key>
```

### Sicherheits-Features

✅ **Rate Limiting:** Max 5 Login-Versuche pro Minute (Brute-Force-Schutz)
✅ **Session-basiert:** Passwort nur beim ersten Besuch eingeben
✅ **HTTPS:** Auf Railway automatisch mit SSL
✅ **Keine Datenbank:** Passwort in Environment Variable

## Nutzung

### Login
1. Öffne deine deployed URL: `https://deine-app.up.railway.app`
2. Passwort eingeben
3. Auf "Anmelden" klicken

### Logout
Entweder:
- Browser schließen (Session läuft ab)
- Manuell: `https://deine-app.up.railway.app/logout` aufrufen

### Session-Timeout
Sessions bleiben aktiv solange der Browser offen ist. Nach Browser-Schließung muss neu eingeloggt werden.

## Passwort ändern

### Lokal:
```bash
# In .env:
APP_PASSWORD=neues-passwort
```

### Railway:
1. Dashboard → Service → Variables
2. `APP_PASSWORD` auf neuen Wert setzen
3. Service wird automatisch neu gestartet

## Sicherheits-Empfehlungen

1. **Starkes Passwort verwenden:**
   ```bash
   # Generiere ein sicheres Passwort:
   python3 -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

2. **Secret Key niemals committen:**
   - `.env` ist in `.gitignore`
   - Nur `.env.example` committen (ohne echte Werte)

3. **HTTPS erzwingen:**
   - Railway macht das automatisch
   - Lokal: Nur für Tests ohne HTTPS

4. **Rate Limiting aktiv:**
   - Bereits implementiert (5 Versuche/Minute)
   - Schützt gegen Brute-Force

## Troubleshooting

### "Falsches Passwort" obwohl richtig?

**Lösung:** Prüfe ob ENV-Variable gesetzt ist:
```bash
# Lokal:
cat .env | grep APP_PASSWORD

# Railway:
# Dashboard → Service → Variables → APP_PASSWORD prüfen
```

### Session läuft sofort ab?

**Lösung:** `SECRET_KEY` muss gesetzt sein und konstant bleiben:
```bash
# Lokal:
cat .env | grep SECRET_KEY

# Railway:
# Prüfe ob SECRET_KEY in Variables gesetzt ist
```

### Rate Limit erreicht?

**Symptom:** "429 Too Many Requests"

**Lösung:** 1 Minute warten, dann erneut versuchen

## API-Zugriff ohne Browser

Falls du die API direkt nutzen willst (z.B. mit curl):

```bash
# 1. Login und Cookie erhalten
curl -c cookies.txt -X POST https://deine-app.railway.app/login \
  -d "password=dein-passwort"

# 2. API mit Cookie nutzen
curl -b cookies.txt https://deine-app.railway.app/api/chat/stream?message=test
```

## Erweiterte Konfiguration

### Session-Timeout ändern

In `app.py` nach der Security Configuration:

```python
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=24)  # 24h statt bis Browser-Schließung
```

### Rate Limits anpassen

In `app.py`:

```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]  # Erhöhen nach Bedarf
)

# Login-Route:
@app.route('/login', methods=['POST'])
@limiter.limit("10 per minute")  # Von 5 auf 10 erhöhen
```

## Support

Bei Problemen:
1. Logs prüfen (Railway: Service → Deployments → Logs)
2. Environment Variables prüfen
3. `.env` Datei prüfen (lokal)
