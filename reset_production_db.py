#!/usr/bin/env python3
"""
Script per resettare il database di produzione del Trading Agent

ATTENZIONE: Questo script eliminerà TUTTI i dati dal database!
- Account snapshots
- Posizioni aperte
- Trade eseguiti
- Contesti AI
- Errori
- Log delle operazioni
- Uso token LLM

Usa con cautela!
"""

import sys
import psycopg2
from datetime import datetime


def confirm_reset():
    """Chiede conferma all'utente prima di procedere"""
    print("=" * 70)
    print("⚠️  ATTENZIONE: RESET DATABASE DI PRODUZIONE")
    print("=" * 70)
    print("\nQuesto script eliminerà TUTTI i dati dalle seguenti tabelle:")
    print("  - account_snapshots")
    print("  - open_positions")
    print("  - executed_trades")
    print("  - bot_operations")
    print("  - ai_contexts")
    print("  - indicators_contexts")
    print("  - forecasts_contexts")
    print("  - news_contexts")
    print("  - sentiment_contexts")
    print("  - llm_usage")
    print("  - errors")
    print("\n⚠️  QUESTA AZIONE È IRREVERSIBILE!")
    print("\nDigita 'RESET PRODUCTION' per confermare: ", end="")

    confirmation = input().strip()

    if confirmation != "RESET PRODUCTION":
        print("\n❌ Reset annullato.")
        return False

    print("\nDigita nuovamente 'YES' per confermare: ", end="")
    second_confirmation = input().strip()

    if second_confirmation != "YES":
        print("\n❌ Reset annullato.")
        return False

    return True


def reset_database():
    """Resetta tutte le tabelle del database"""

    # Configurazione database
    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'trading_db',
        'user': 'trading_user',
        'password': 'DontUseWeakPassword123'
    }

    print("\n" + "=" * 70)
    print(f"🔄 Avvio reset database: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    try:
        # Connessione al database
        print("\n📡 Connessione al database...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cur = conn.cursor()

        print("✅ Connessione stabilita")

        # Lista delle tabelle da resettare (in ordine per rispettare le foreign keys)
        tables_to_reset = [
            'indicators_contexts',
            'forecasts_contexts',
            'news_contexts',
            'sentiment_contexts',
            'ai_contexts',
            'open_positions',
            'executed_trades',
            'bot_operations',
            'llm_usage',
            'errors',
            'account_snapshots'
        ]

        print(f"\n🗑️  Eliminazione dati da {len(tables_to_reset)} tabelle...")

        deleted_counts = {}

        for table in tables_to_reset:
            try:
                # Conta i record prima dell'eliminazione
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]

                if count > 0:
                    # Elimina tutti i record
                    cur.execute(f"DELETE FROM {table}")
                    deleted_counts[table] = count
                    print(f"  ✅ {table}: {count} record eliminati")
                else:
                    print(f"  ⚪ {table}: già vuota")

            except psycopg2.Error as e:
                print(f"  ❌ {table}: Errore - {e}")
                raise

        # Reset delle sequenze (per far ripartire gli ID da 1)
        print("\n🔄 Reset sequenze ID...")
        sequences = [
            'account_snapshots_id_seq',
            'open_positions_id_seq',
            'executed_trades_id_seq',
            'bot_operations_id_seq',
            'ai_contexts_id_seq',
            'indicators_contexts_id_seq',
            'forecasts_contexts_id_seq',
            'news_contexts_id_seq',
            'sentiment_contexts_id_seq',
            'llm_usage_id_seq',
            'errors_id_seq'
        ]

        for seq in sequences:
            try:
                cur.execute(f"ALTER SEQUENCE {seq} RESTART WITH 1")
                print(f"  ✅ {seq} resettata")
            except psycopg2.Error:
                # Alcune sequenze potrebbero non esistere
                print(f"  ⚪ {seq} non trovata (OK)")

        # Commit delle modifiche
        print("\n💾 Salvataggio modifiche...")
        conn.commit()
        print("✅ Modifiche salvate")

        # Riepilogo
        print("\n" + "=" * 70)
        print("📊 RIEPILOGO RESET")
        print("=" * 70)

        total_deleted = sum(deleted_counts.values())
        print(f"\nTotale record eliminati: {total_deleted}")
        print("\nDettaglio per tabella:")
        for table, count in deleted_counts.items():
            print(f"  • {table}: {count}")

        print("\n✅ Database resettato con successo!")
        print("🚀 Il trading agent ripartirà con dati puliti al prossimo ciclo")

        # Chiusura connessione
        cur.close()
        conn.close()

        return True

    except psycopg2.Error as e:
        print(f"\n❌ Errore database: {e}")
        if conn:
            conn.rollback()
            print("🔄 Rollback eseguito - nessuna modifica applicata")
        return False

    except Exception as e:
        print(f"\n❌ Errore: {e}")
        if conn:
            conn.rollback()
            print("🔄 Rollback eseguito - nessuna modifica applicata")
        return False

    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("\n📡 Connessione chiusa")


def main():
    """Main function"""
    print("\n🤖 Trading Agent - Database Reset Utility")
    print("=" * 70)

    # Controlla se lo script viene eseguito sulla VPS
    print("\n⚠️  IMPORTANTE: Questo script deve essere eseguito SULLA VPS")
    print("Esegui: ssh n8n 'cd trading-agent && python3 reset_production_db.py'")
    print("\nOppure:")
    print("1. ssh n8n")
    print("2. cd trading-agent")
    print("3. python3 reset_production_db.py")
    print("\n" + "=" * 70)

    # Chiedi conferma
    if not confirm_reset():
        sys.exit(0)

    # Esegui il reset
    success = reset_database()

    if success:
        print("\n" + "=" * 70)
        print("✅ RESET COMPLETATO")
        print("=" * 70)
        print("\nProssimi passi:")
        print("1. Il trading engine creerà nuovi snapshot automaticamente")
        print("2. I dati inizieranno ad accumularsi dal prossimo ciclo")
        print("3. Verifica il dashboard per confermare il reset")
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("❌ RESET FALLITO")
        print("=" * 70)
        print("\nControlla i log per dettagli sull'errore")
        sys.exit(1)


if __name__ == "__main__":
    main()
