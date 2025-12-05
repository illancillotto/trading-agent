# Istruzioni per Deploy in Produzione (via SSH/n8n)

## Problema
Quando si esegue `docker compose -f docker-compose.prod.yml` direttamente, le variabili d'ambiente non vengono caricate correttamente perché Docker Compose non legge automaticamente `backend/.env` per le sostituzioni nelle sezioni `environment:`.

## Soluzione 1: Usare lo Script di Deploy (Raccomandato)

Lo script `production-deploy.sh` carica automaticamente le variabili da `backend/.env`:

```bash
./production-deploy.sh
```

## Soluzione 2: Creare un file .env nella Root

Se vuoi eseguire `docker compose` direttamente, crea un file `.env` nella root del progetto che Docker Compose può leggere automaticamente:

```bash
# Sul server di produzione, esegui:
cd ~/trading-agent

# Crea un file .env nella root con le variabili necessarie
cat > .env << 'EOF'
POSTGRES_PASSWORD=$(grep POSTGRES_PASSWORD backend/.env | cut -d'=' -f2)
DB_PASSWORD=$(grep DB_PASSWORD backend/.env | cut -d'=' -f2)
EOF

# Oppure copia direttamente le variabili necessarie:
grep -E "^(POSTGRES_PASSWORD|DB_PASSWORD|MASTER_ACCOUNT_ADDRESS|PRIVATE_KEY|WALLET_ADDRESS|COINGECKO_API_KEY)=" backend/.env > .env
```

Poi puoi eseguire:
```bash
docker compose -f docker-compose.prod.yml up -d
```

## Soluzione 3: Esportare le Variabili Manualmente

Prima di eseguire docker compose, esporta le variabili:

```bash
# Carica le variabili da backend/.env
set -a
source backend/.env
set +a

# Override per produzione
export POSTGRES_HOST=db
export DATABASE_URL=postgresql://trading_user:${POSTGRES_PASSWORD}@db:5432/trading_db
export ENVIRONMENT=production

# Ora puoi eseguire docker compose
docker compose -f docker-compose.prod.yml up -d
```

## Verifica

Dopo il deploy, verifica che i container siano in esecuzione:

```bash
docker compose -f docker-compose.prod.yml ps
```

Dovresti vedere:
- `trading-db-prod` (database)
- `trading-agent-prod` (applicazione)
- `trading-nginx-prod` (reverse proxy)

## Accesso alla Dashboard

La dashboard dovrebbe essere accessibile su:
- **HTTP**: `http://91.98.126.9` (porta 80, gestita da nginx)
- **Diretto**: `http://91.98.126.9:5611` (se esponi la porta direttamente)

## Troubleshooting

### Se i container non si avviano:

1. Verifica i log:
   ```bash
   docker compose -f docker-compose.prod.yml logs
   ```

2. Verifica che le variabili siano caricate:
   ```bash
   echo $POSTGRES_PASSWORD
   ```

3. Verifica che il file .env esista:
   ```bash
   ls -la backend/.env
   ```

### Se vedi errori di connessione al database:

Verifica che `POSTGRES_PASSWORD` sia impostato correttamente in `backend/.env`:
```bash
grep POSTGRES_PASSWORD backend/.env
```


