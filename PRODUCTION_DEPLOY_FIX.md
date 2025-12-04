# Fix per il Deploy in Produzione

## Problemi Identificati e Risolti

### 1. ✅ Configurazione Nginx senza SSL
- **Problema**: Nginx richiedeva certificati SSL che non erano disponibili
- **Soluzione**: Configurato Nginx per funzionare in HTTP (porta 80) senza SSL. I certificati SSL possono essere aggiunti successivamente

### 2. ✅ Path dei File Statici
- **Problema**: I file statici del frontend erano copiati in `/app/static` ma l'applicazione li cercava in `/app/backend/static`
- **Soluzione**: Modificato `Dockerfile.prod` per copiare i file statici in `./backend/static`

### 3. ✅ Variabili d'Ambiente
- **Problema**: `docker-compose.prod.yml` non caricava le variabili d'ambiente da `backend/.env`
- **Soluzione**: Aggiunto `env_file: - backend/.env` ai servizi `app` e `db`

### 4. ✅ Attributo Version Obsoleto
- **Problema**: Docker Compose mostrava warning per l'attributo `version` obsoleto
- **Soluzione**: Rimosso l'attributo `version` da entrambi i file docker-compose

## Istruzioni per il Deploy

### 1. Fermare i Container di Sviluppo
Se hai avviato i container di sviluppo, fermali prima:
```bash
docker-compose down
```

### 2. Eseguire il Deploy di Produzione
```bash
./production-deploy.sh
```

### 3. Verificare i Container
```bash
docker compose -f docker-compose.prod.yml ps
```

Dovresti vedere:
- `trading-db-prod` (database)
- `trading-agent-prod` (applicazione)
- `trading-nginx-prod` (reverse proxy)

### 4. Verificare i Log
```bash
# Log dell'applicazione
docker compose -f docker-compose.prod.yml logs app --tail 50

# Log di nginx
docker compose -f docker-compose.prod.yml logs nginx --tail 50
```

### 5. Accedere alla Dashboard
La dashboard dovrebbe essere accessibile su:
- **HTTP**: `http://91.98.126.9` (porta 80, gestita da nginx)
- **Diretto (solo per test)**: `http://91.98.126.9:5611` (se esponi la porta)

**Nota**: Se stai usando una porta diversa (es. 5621), potrebbe essere configurata da un firewall o reverse proxy esterno.

## Configurazione Porte

### Produzione (con Nginx)
- **Porta 80**: Nginx (HTTP) → Proxy verso app:5611
- **Porta 443**: Nginx (HTTPS) - Disponibile quando aggiungi certificati SSL

### Accesso Diretto (solo per debug)
Se vuoi accedere direttamente all'app senza nginx, puoi aggiungere questa sezione al servizio `app` in `docker-compose.prod.yml`:
```yaml
ports:
  - "5611:5611"
```

**Nota**: Non è raccomandato in produzione, usa sempre nginx.

## Troubleshooting

### Se la dashboard non è accessibile:

1. **Verifica che i container siano in esecuzione**:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```

2. **Verifica i log di nginx**:
   ```bash
   docker compose -f docker-compose.prod.yml logs nginx
   ```

3. **Verifica che l'app risponda**:
   ```bash
   docker compose -f docker-compose.prod.yml exec app curl http://localhost:5611/api/health
   ```

4. **Verifica che nginx possa raggiungere l'app**:
   ```bash
   docker compose -f docker-compose.prod.yml exec nginx curl http://app:5611/api/health
   ```

5. **Verifica i file statici**:
   ```bash
   docker compose -f docker-compose.prod.yml exec app ls -la /app/backend/static/
   ```

### Se vedi errori 404:
- Verifica che i file statici siano stati costruiti correttamente durante il build
- Controlla che il path in `main.py` corrisponda a quello nel container

### Se vedi errori di connessione:
- Verifica che il firewall permetta il traffico sulla porta 80
- Controlla che nginx sia in esecuzione e possa raggiungere l'app

## Aggiungere SSL in Futuro

Quando vuoi aggiungere SSL:

1. Ottieni i certificati SSL e mettili in `./ssl/production/`
2. Modifica `nginx/nginx.conf` per abilitare il blocco HTTPS (commentato)
3. Riavvia nginx:
   ```bash
   docker compose -f docker-compose.prod.yml restart nginx
   ```

