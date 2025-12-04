#!/bin/bash
#
# Script per resettare il database di produzione del Trading Agent
#
# ATTENZIONE: Questo script eliminerà TUTTI i dati dal database!
#

set -e

echo "======================================================================"
echo "⚠️  ATTENZIONE: RESET DATABASE DI PRODUZIONE"
echo "======================================================================"
echo ""
echo "Questo script eliminerà TUTTI i dati dalle seguenti tabelle:"
echo "  - account_snapshots"
echo "  - open_positions"
echo "  - executed_trades"
echo "  - bot_operations"
echo "  - ai_contexts"
echo "  - indicators_contexts"
echo "  - forecasts_contexts"
echo "  - news_contexts"
echo "  - sentiment_contexts"
echo "  - llm_usage"
echo "  - errors"
echo ""
echo "⚠️  QUESTA AZIONE È IRREVERSIBILE!"
echo ""
read -p "Digita 'RESET PRODUCTION' per confermare: " confirmation

if [ "$confirmation" != "RESET PRODUCTION" ]; then
    echo ""
    echo "❌ Reset annullato."
    exit 0
fi

echo ""
read -p "Digita nuovamente 'YES' per confermare: " second_confirmation

if [ "$second_confirmation" != "YES" ]; then
    echo ""
    echo "❌ Reset annullato."
    exit 0
fi

echo ""
echo "======================================================================"
echo "🔄 Avvio reset database: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"
echo ""

# SQL per contare i record prima dell'eliminazione
echo "📊 Conteggio record attuali..."
docker exec trading-db-prod psql -U trading_user -d trading_db << 'EOSQL'
SELECT
    'account_snapshots' as tabella,
    COUNT(*) as records
FROM account_snapshots
UNION ALL
SELECT 'open_positions', COUNT(*) FROM open_positions
UNION ALL
SELECT 'executed_trades', COUNT(*) FROM executed_trades
UNION ALL
SELECT 'bot_operations', COUNT(*) FROM bot_operations
UNION ALL
SELECT 'ai_contexts', COUNT(*) FROM ai_contexts
UNION ALL
SELECT 'indicators_contexts', COUNT(*) FROM indicators_contexts
UNION ALL
SELECT 'forecasts_contexts', COUNT(*) FROM forecasts_contexts
UNION ALL
SELECT 'news_contexts', COUNT(*) FROM news_contexts
UNION ALL
SELECT 'sentiment_contexts', COUNT(*) FROM sentiment_contexts
UNION ALL
SELECT 'llm_usage', COUNT(*) FROM llm_usage
UNION ALL
SELECT 'errors', COUNT(*) FROM errors;
EOSQL

echo ""
echo "🗑️  Eliminazione dati..."

# SQL per eliminare tutti i dati (rispettando le foreign keys)
docker exec trading-db-prod psql -U trading_user -d trading_db << 'EOSQL'
BEGIN;

-- Elimina in ordine per rispettare foreign keys
DELETE FROM indicators_contexts;
DELETE FROM forecasts_contexts;
DELETE FROM news_contexts;
DELETE FROM sentiment_contexts;
DELETE FROM ai_contexts;
DELETE FROM open_positions;
DELETE FROM executed_trades;
DELETE FROM bot_operations;
DELETE FROM llm_usage;
DELETE FROM errors;
DELETE FROM account_snapshots;

-- Reset sequenze (per far ripartire gli ID da 1)
ALTER SEQUENCE account_snapshots_id_seq RESTART WITH 1;
ALTER SEQUENCE open_positions_id_seq RESTART WITH 1;
ALTER SEQUENCE executed_trades_id_seq RESTART WITH 1;
ALTER SEQUENCE bot_operations_id_seq RESTART WITH 1;
ALTER SEQUENCE ai_contexts_id_seq RESTART WITH 1;
ALTER SEQUENCE indicators_contexts_id_seq RESTART WITH 1;
ALTER SEQUENCE forecasts_contexts_id_seq RESTART WITH 1;
ALTER SEQUENCE news_contexts_id_seq RESTART WITH 1;
ALTER SEQUENCE sentiment_contexts_id_seq RESTART WITH 1;
ALTER SEQUENCE llm_usage_id_seq RESTART WITH 1;
ALTER SEQUENCE errors_id_seq RESTART WITH 1;

COMMIT;

-- Verifica che tutte le tabelle siano vuote
SELECT
    'account_snapshots' as tabella,
    COUNT(*) as records
FROM account_snapshots
UNION ALL
SELECT 'open_positions', COUNT(*) FROM open_positions
UNION ALL
SELECT 'executed_trades', COUNT(*) FROM executed_trades
UNION ALL
SELECT 'bot_operations', COUNT(*) FROM bot_operations
UNION ALL
SELECT 'ai_contexts', COUNT(*) FROM ai_contexts
UNION ALL
SELECT 'indicators_contexts', COUNT(*) FROM indicators_contexts
UNION ALL
SELECT 'forecasts_contexts', COUNT(*) FROM forecasts_contexts
UNION ALL
SELECT 'news_contexts', COUNT(*) FROM news_contexts
UNION ALL
SELECT 'sentiment_contexts', COUNT(*) FROM sentiment_contexts
UNION ALL
SELECT 'llm_usage', COUNT(*) FROM llm_usage
UNION ALL
SELECT 'errors', COUNT(*) FROM errors;
EOSQL

echo ""
echo "======================================================================"
echo "✅ RESET COMPLETATO"
echo "======================================================================"
echo ""
echo "Prossimi passi:"
echo "1. Il trading engine creerà nuovi snapshot automaticamente"
echo "2. I dati inizieranno ad accumularsi dal prossimo ciclo"
echo "3. Verifica il dashboard per confermare il reset"
echo ""
echo "🚀 Database pulito e pronto per ripartire!"
echo ""
