# Frontend Update Guide

Guida per aggiornare il frontend del Trading Agent.

## 📋 Scripts Disponibili

### 1. `update-frontend.sh` - Uso Generale
Script per buildare il frontend localmente o su server.

**Uso:**
```bash
./update-frontend.sh
```

**Cosa fa:**
- Builda il frontend con npm
- Copia i file in `backend/static/`
- Mostra istruzioni per riavviare il servizio

### 2. `update-frontend-vps.sh` - Uso VPS (Raccomandato)
Script automatico per VPS con Docker.

**Uso:**
```bash
./update-frontend-vps.sh
```

**Cosa fa:**
- Builda il frontend
- Copia i file nella posizione corretta
- Riavvia automaticamente il servizio Docker
- Mostra l'URL della dashboard

---

## 🚀 Aggiornamento Rapido

### Su VPS (con Docker)

```bash
# Connettiti alla VPS
ssh root@your-vps-ip

# Vai nella directory del progetto
cd /root/trading-agent  # o la tua directory

# Pull delle modifiche (se hai pushato)
git pull

# Esegui lo script
./update-frontend-vps.sh
```

### In Locale

```bash
# Vai nella directory del progetto
cd /path/to/trading-agent

# Esegui lo script
./update-frontend.sh

# Refresh browser con Ctrl+Shift+R
```

---

## 🛠️ Aggiornamento Manuale

Se preferisci fare i passaggi manualmente:

### 1. Build Frontend
```bash
cd frontend
npm run build
```

### 2. Copia Files
```bash
cd ..
mkdir -p backend/static
cp -r static/* backend/static/
```

### 3. Riavvia Servizio
```bash
# Con Docker
docker-compose restart app
# oppure
docker-compose -f docker-compose.prod.yml restart app
```

### 4. Refresh Browser
Apri la dashboard e premi `Ctrl+Shift+R` (hard refresh)

---

## ✅ Verifica

Dopo l'aggiornamento, verifica che:

1. **Dashboard carica correttamente** su `http://your-ip:5611`
2. **Coin Screener mostra "✅ Abilitato"** nella sezione Configurazione Sistema
3. **Operazioni recenti** mostrano tutti i trade (incluso ADA)
4. **Cronologia Decisioni AI** è aggiornata

---

## 🆘 Troubleshooting

### Problema: Frontend ancora vecchio
**Soluzione:**
```bash
# 1. Cancella cache browser (Ctrl+Shift+Delete)
# 2. Hard refresh (Ctrl+Shift+R)
# 3. Riavvia completamente Docker
docker-compose down
docker-compose up -d
```

### Problema: "Permission denied"
**Soluzione:**
```bash
chmod +x update-frontend-vps.sh
# oppure esegui con sudo
sudo ./update-frontend-vps.sh
```

### Problema: "npm: command not found"
**Soluzione:**
```bash
# Installa Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Problema: Files non copiati
**Soluzione:**
```bash
# Verifica che i file esistano
ls -la static/
ls -la backend/static/

# Se non ci sono, rebuilda
cd frontend
npm run build
cd ..
cp -r static/* backend/static/
```

---

## 📝 Note

- Gli script sono safe e non modificano il codice sorgente
- Puoi eseguirli ogni volta che aggiorni il frontend
- Su VPS, lo script riavvia automaticamente solo il container `app`
- I dati del trading agent non vengono toccati

---

## 🎯 Workflow Consigliato

1. **Sviluppo locale**: Modifica il frontend
2. **Test locale**: `./update-frontend.sh` + refresh browser
3. **Commit e push**: `git add . && git commit -m "Update frontend" && git push`
4. **Deploy su VPS**:
   ```bash
   ssh root@vps
   cd trading-agent
   git pull
   ./update-frontend-vps.sh
   ```

---

Made with ❤️ for Trading Agent
