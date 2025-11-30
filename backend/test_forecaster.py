"""
Test suite per il modulo forecaster.py
Testa sia HybridForecaster (LSTM+ARIMA) che HyperliquidForecaster (Prophet)
"""
import sys
import os
import warnings
import time
from datetime import datetime, timezone
import pandas as pd
import numpy as np

# Aggiungi il path per gli import
sys.path.append(os.path.dirname(__file__))

try:
    from forecaster import (
        HybridForecaster,
        HyperliquidForecaster,
        get_crypto_forecasts,
        _format_forecast_text,
        _convert_to_legacy_format,
        ARIMA_AVAILABLE,
        TORCH_AVAILABLE
    )
except ImportError as e:
    print(f"❌ Errore import forecaster: {e}")
    print("Assicurati di aver installato tutte le dipendenze:")
    print("  - hyperliquid-python-sdk")
    print("  - prophet")
    print("  - statsmodels (opzionale)")
    print("  - torch (opzionale)")
    sys.exit(1)

warnings.filterwarnings('ignore')

# -------------------------------------------------------------------
#                    CONFIG PANEL
# -------------------------------------------------------------------
TESTNET = True  # True = testnet, False = mainnet
VERBOSE = True  # stampa informazioni extra
USE_REAL_DATA = True  # Se False, usa solo test mock
TEST_TICKERS = ['BTC', 'ETH']  # Ticker da testare
TEST_INTERVALS = ['15m', '1h']  # Intervalli da testare


# -------------------------------------------------------------------
#                    HELPER FUNCTIONS
# -------------------------------------------------------------------
def print_section(title: str):
    """Stampa un'intestazione di sezione"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_test(name: str):
    """Stampa il nome di un test"""
    print(f"\n🧪 Test: {name}")


def print_success(msg: str = "OK"):
    """Stampa un messaggio di successo"""
    print(f"✅ {msg}")


def print_error(msg: str):
    """Stampa un messaggio di errore"""
    print(f"❌ {msg}")


def print_warning(msg: str):
    """Stampa un messaggio di warning"""
    print(f"⚠️  {msg}")


def print_info(msg: str):
    """Stampa un messaggio informativo"""
    if VERBOSE:
        print(f"ℹ️  {msg}")


# -------------------------------------------------------------------
#                    TEST FUNCTIONS
# -------------------------------------------------------------------
def test_imports():
    """Test che tutte le librerie necessarie siano importabili"""
    print_test("Verifica import librerie")
    
    issues = []
    
    if not ARIMA_AVAILABLE:
        issues.append("statsmodels non disponibile")
    else:
        print_success("statsmodels disponibile")
    
    if not TORCH_AVAILABLE:
        issues.append("torch non disponibile")
    else:
        print_success("torch disponibile")
    
    try:
        from prophet import Prophet
        print_success("prophet disponibile")
    except ImportError:
        issues.append("prophet non disponibile")
    
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        print_success("hyperliquid-python-sdk disponibile")
    except ImportError:
        issues.append("hyperliquid-python-sdk non disponibile")
    
    if issues:
        print_warning(f"Librerie mancanti: {', '.join(issues)}")
        print_warning("Alcuni test potrebbero fallire o usare fallback")
        # Non considerare come fallito se mancano solo alcune librerie opzionali
        return True  # Considera sempre passato, è solo informativo
    else:
        print_success("Tutte le librerie disponibili")
    
    return True


def test_hybrid_forecaster_init():
    """Test inizializzazione HybridForecaster"""
    print_test("Inizializzazione HybridForecaster")
    
    try:
        forecaster = HybridForecaster(testnet=TESTNET)
        print_success("HybridForecaster inizializzato correttamente")
        print_info(f"Device: {forecaster.device}")
        print_info(f"Use GPU: {forecaster.use_gpu}")
        return True
    except ImportError as e:
        if "hyperliquid" in str(e).lower():
            print_warning("Hyperliquid non disponibile, test saltato")
            return "SKIPPED"  # Usa stringa speciale per indicare skip
        print_error(f"Errore import: {e}")
        return False
    except Exception as e:
        print_error(f"Errore inizializzazione: {e}")
        return False


def test_hyperliquid_forecaster_init():
    """Test inizializzazione HyperliquidForecaster"""
    print_test("Inizializzazione HyperliquidForecaster")
    
    try:
        forecaster = HyperliquidForecaster(testnet=TESTNET)
        print_success("HyperliquidForecaster inizializzato correttamente")
        return True
    except ImportError as e:
        if "hyperliquid" in str(e).lower() or "prophet" in str(e).lower():
            print_warning("Librerie richieste non disponibili, test saltato")
            return "SKIPPED"
        print_error(f"Errore import: {e}")
        return False
    except Exception as e:
        print_error(f"Errore inizializzazione: {e}")
        return False


def test_fetch_candles():
    """Test recupero candele da Hyperliquid"""
    print_test("Recupero candele da Hyperliquid")
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return True
    
    try:
        forecaster = HybridForecaster(testnet=TESTNET)
        
        for ticker in TEST_TICKERS[:1]:  # Test solo il primo per velocità
            for interval in TEST_INTERVALS:
                print_info(f"Recupero {ticker} {interval}...")
                df = forecaster._fetch_candles(ticker, interval, limit=100)
                
                assert len(df) > 0, f"Nessun dato per {ticker} {interval}"
                assert 'timestamp' in df.columns, "Colonna 'timestamp' mancante"
                assert 'close' in df.columns, "Colonna 'close' mancante"
                
                print_success(f"{ticker} {interval}: {len(df)} candele recuperate")
                print_info(f"  Range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
                print_info(f"  Prezzo: ${df['close'].iloc[-1]:.2f}")
        
        return True
    except ImportError as e:
        if "hyperliquid" in str(e).lower():
            print_warning("Hyperliquid non disponibile, test saltato")
            return "SKIPPED"
        raise
    except Exception as e:
        print_error(f"Errore recupero candele: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_arima_training():
    """Test training modello ARIMA con dati reali da Hyperliquid"""
    print_test("Training modello ARIMA (dati reali)")
    
    if not ARIMA_AVAILABLE:
        print_warning("ARIMA non disponibile, test saltato")
        return "SKIPPED"
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return "SKIPPED"
    
    try:
        # Crea forecaster per recuperare dati reali
        try:
            forecaster = HybridForecaster(testnet=TESTNET)
        except ImportError as e:
            if "hyperliquid" in str(e).lower():
                print_warning("Hyperliquid non disponibile, test saltato")
                return "SKIPPED"
            raise
        
        # Recupera dati reali da Hyperliquid
        ticker = TEST_TICKERS[0]
        interval = TEST_INTERVALS[0]
        
        print_info(f"Recupero dati reali per {ticker} {interval}...")
        df = forecaster._fetch_candles(ticker, interval, limit=200)
        prices = df["close"].values
        
        if len(prices) < 50:
            print_error(f"Dati insufficienti: solo {len(prices)} punti")
            return False
        
        print_success(f"Recuperati {len(prices)} punti dati")
        print_info(f"Range prezzi: ${prices.min():.2f} - ${prices.max():.2f}")
        print_info(f"Ultimo prezzo: ${prices[-1]:.2f}")
        
        # Test training ARIMA
        print_info("Addestramento ARIMA su dati reali...")
        start_time = time.time()
        model = forecaster._train_arima(prices)
        elapsed = time.time() - start_time
        
        if model is not None:
            print_success(f"ARIMA addestrato in {elapsed:.2f}s")
            print_info(f"AIC: {model.aic:.2f}")
            
            # Test previsione
            prediction = forecaster._predict_arima(model, steps=1)
            if prediction is not None:
                last_price = prices[-1]
                pct_change = ((prediction - last_price) / last_price) * 100
                
                print_success(f"Previsione ARIMA: ${prediction:.2f}")
                print_info(f"Ultimo prezzo: ${last_price:.2f}")
                print_info(f"Variazione prevista: {pct_change:+.2f}%")
                
                # Verifica che la previsione sia ragionevole
                price_std = prices.std()
                if abs(prediction - last_price) > price_std * 5:
                    print_warning(f"Previsione sembra fuori range (diff: {abs(prediction - last_price):.2f}, std: {price_std:.2f})")
                else:
                    print_success("Previsione ARIMA ragionevole")
                
                # Verifica tempo di training
                if elapsed > 10:
                    print_warning(f"Tempo di training ({elapsed:.2f}s) supera il target di 10s")
                else:
                    print_success(f"Tempo di training accettabile: {elapsed:.2f}s")
                
                return True
            else:
                print_error("Previsione ARIMA fallita (None)")
                return False
        else:
            print_error("ARIMA non addestrato - nessun modello valido trovato")
            return False
        
    except Exception as e:
        print_error(f"Errore training ARIMA: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_lstm_training():
    """Test training modello LSTM con dati reali da Hyperliquid"""
    print_test("Training modello LSTM (dati reali)")
    
    if not TORCH_AVAILABLE:
        print_warning("PyTorch non disponibile, test saltato")
        return "SKIPPED"
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return "SKIPPED"
    
    try:
        # Crea forecaster per recuperare dati reali
        try:
            forecaster = HybridForecaster(testnet=TESTNET)
        except ImportError as e:
            if "hyperliquid" in str(e).lower():
                print_warning("Hyperliquid non disponibile, test saltato")
                return "SKIPPED"
            raise
        
        # Recupera dati reali da Hyperliquid
        ticker = TEST_TICKERS[0]
        interval = TEST_INTERVALS[0]
        
        print_info(f"Recupero dati reali per {ticker} {interval}...")
        df = forecaster._fetch_candles(ticker, interval, limit=200)
        prices = df["close"].values
        
        if len(prices) < 50:
            print_error(f"Dati insufficienti: solo {len(prices)} punti")
            return False
        
        print_success(f"Recuperati {len(prices)} punti dati")
        print_info(f"Range prezzi: ${prices.min():.2f} - ${prices.max():.2f}")
        print_info(f"Ultimo prezzo: ${prices[-1]:.2f}")
        
        # Test training LSTM
        print_info("Addestramento LSTM su dati reali...")
        start_time = time.time()
        model, scaler = forecaster._train_lstm(prices, epochs=15, sequence_length=20)
        elapsed = time.time() - start_time
        
        if model is not None and scaler is not None:
            print_success(f"LSTM addestrato in {elapsed:.2f}s")
            
            # Test previsione
            last_sequence = prices[-20:]
            prediction = forecaster._predict_lstm(model, scaler, last_sequence)
            
            if prediction is not None:
                last_price = prices[-1]
                pct_change = ((prediction - last_price) / last_price) * 100
                
                print_success(f"Previsione LSTM: ${prediction:.2f}")
                print_info(f"Ultimo prezzo: ${last_price:.2f}")
                print_info(f"Variazione prevista: {pct_change:+.2f}%")
                
                # Verifica che la previsione sia ragionevole
                price_std = prices.std()
                if abs(prediction - last_price) > price_std * 5:
                    print_warning(f"Previsione sembra fuori range (diff: {abs(prediction - last_price):.2f}, std: {price_std:.2f})")
                else:
                    print_success("Previsione LSTM ragionevole")
                
                # Verifica tempo di training
                if elapsed > 10:
                    print_warning(f"Tempo di training ({elapsed:.2f}s) supera il target di 10s")
                else:
                    print_success(f"Tempo di training accettabile: {elapsed:.2f}s")
                
                return True
            else:
                print_error("Previsione LSTM fallita (None)")
                return False
        else:
            print_error("LSTM non addestrato o scaler mancante")
            return False
        
    except Exception as e:
        print_error(f"Errore training LSTM: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hybrid_forecast():
    """Test previsione ibrida completa"""
    print_test("Previsione ibrida (LSTM+ARIMA)")
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return True
    
    try:
        try:
            forecaster = HybridForecaster(testnet=TESTNET)
        except ImportError as e:
            if "hyperliquid" in str(e).lower():
                print_warning("Hyperliquid non disponibile, test saltato")
                return True
            raise
        
        ticker = TEST_TICKERS[0]
        interval = TEST_INTERVALS[0]
        
        print_info(f"Previsione per {ticker} {interval}...")
        start_time = time.time()
        result = forecaster.forecast(ticker, interval)
        elapsed = time.time() - start_time
        
        assert result is not None, "Risultato previsione è None"
        assert 'symbol' in result, "Campo 'symbol' mancante"
        assert 'forecast_price' in result, "Campo 'forecast_price' mancante"
        assert 'pct_change' in result, "Campo 'pct_change' mancante"
        assert 'model_used' in result, "Campo 'model_used' mancante"
        
        print_success(f"Previsione completata in {elapsed:.2f}s")
        print_info(f"  Symbol: {result['symbol']}")
        print_info(f"  Interval: {result['interval']}")
        print_info(f"  Last Price: ${result.get('last_price', 'N/A')}")
        print_info(f"  Forecast Price: ${result['forecast_price']}")
        print_info(f"  % Change: {result['pct_change']:+.2f}%")
        print_info(f"  Model: {result['model_used']}")
        
        # Verifica che il tempo sia ragionevole (< 10s come richiesto)
        if elapsed > 10:
            print_warning(f"Tempo di previsione ({elapsed:.2f}s) supera il target di 10s")
        else:
            print_success(f"Tempo di previsione accettabile: {elapsed:.2f}s")
        
        return True
    except Exception as e:
        print_error(f"Errore previsione ibrida: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_forecast_many():
    """Test previsioni multiple"""
    print_test("Previsioni multiple (forecast_many)")
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return True
    
    try:
        try:
            forecaster = HybridForecaster(testnet=TESTNET)
        except ImportError as e:
            if "hyperliquid" in str(e).lower():
                print_warning("Hyperliquid non disponibile, test saltato")
                return True
            raise
        
        print_info(f"Previsioni per {TEST_TICKERS} su {TEST_INTERVALS}...")
        start_time = time.time()
        results = forecaster.forecast_many(TEST_TICKERS, intervals=TEST_INTERVALS)
        elapsed = time.time() - start_time
        
        assert len(results) > 0, "Nessun risultato"
        assert len(results) == len(TEST_TICKERS) * len(TEST_INTERVALS), \
            f"Numero risultati errato: attesi {len(TEST_TICKERS) * len(TEST_INTERVALS)}, ottenuti {len(results)}"
        
        print_success(f"{len(results)} previsioni completate in {elapsed:.2f}s")
        
        for result in results:
            if result.get('forecast_price') is not None:
                print_info(f"  {result['symbol']} {result['interval']}: "
                          f"${result['forecast_price']} ({result['pct_change']:+.2f}%) "
                          f"[{result['model_used']}]")
            else:
                print_warning(f"  {result['symbol']} {result['interval']}: ERRORE")
        
        return True
    except Exception as e:
        print_error(f"Errore previsioni multiple: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prophet_forecast():
    """Test previsione con Prophet (fallback)"""
    print_test("Previsione Prophet (fallback)")
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return True
    
    try:
        try:
            forecaster = HyperliquidForecaster(testnet=TESTNET)
        except ImportError as e:
            if "hyperliquid" in str(e).lower() or "prophet" in str(e).lower():
                print_warning("Librerie richieste non disponibili, test saltato")
                return True
            raise
        
        ticker = TEST_TICKERS[0]
        interval = TEST_INTERVALS[0]
        
        print_info(f"Previsione Prophet per {ticker} {interval}...")
        start_time = time.time()
        forecast_data, last_price = forecaster.forecast(ticker, interval)
        elapsed = time.time() - start_time
        
        assert forecast_data is not None, "Dati previsione Prophet sono None"
        assert last_price is not None, "Ultimo prezzo è None"
        
        fc = forecast_data.iloc[0]
        print_success(f"Previsione Prophet completata in {elapsed:.2f}s")
        print_info(f"  Last Price: ${last_price:.2f}")
        print_info(f"  Forecast: ${fc['yhat']:.2f}")
        print_info(f"  Lower: ${fc['yhat_lower']:.2f}")
        print_info(f"  Upper: ${fc['yhat_upper']:.2f}")
        
        return True
    except Exception as e:
        print_error(f"Errore previsione Prophet: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_crypto_forecasts_hybrid():
    """Test funzione get_crypto_forecasts con modello ibrido"""
    print_test("get_crypto_forecasts (modello ibrido)")
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return True
    
    try:
        print_info("Chiamata get_crypto_forecasts con use_hybrid=True...")
        start_time = time.time()
        text_output, json_output = get_crypto_forecasts(
            tickers=TEST_TICKERS,
            testnet=TESTNET,
            use_hybrid=True
        )
        elapsed = time.time() - start_time
        
        assert text_output is not None, "Output testo è None"
        assert json_output is not None, "Output JSON è None"
        assert isinstance(json_output, list), "Output JSON non è una lista"
        
        print_success(f"get_crypto_forecasts completata in {elapsed:.2f}s")
        print_info("\nOutput testo:")
        print(text_output)
        print_info(f"\nOutput JSON ({len(json_output)} elementi):")
        for item in json_output[:3]:  # Mostra solo i primi 3
            print(f"  {item}")
        
        # Verifica formato JSON
        for item in json_output:
            assert 'symbol' in item, "Campo 'symbol' mancante in JSON"
            assert 'interval' in item, "Campo 'interval' mancante in JSON"
            assert 'forecast_price' in item, "Campo 'forecast_price' mancante in JSON"
            assert 'pct_change' in item, "Campo 'pct_change' mancante in JSON"
            assert 'model_used' in item, "Campo 'model_used' mancante in JSON"
        
        print_success("Formato JSON valido")
        return True
    except Exception as e:
        print_error(f"Errore get_crypto_forecasts: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_crypto_forecasts_prophet():
    """Test funzione get_crypto_forecasts con Prophet"""
    print_test("get_crypto_forecasts (Prophet fallback)")
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return True
    
    try:
        print_info("Chiamata get_crypto_forecasts con use_hybrid=False...")
        start_time = time.time()
        text_output, json_output = get_crypto_forecasts(
            tickers=TEST_TICKERS,
            testnet=TESTNET,
            use_hybrid=False
        )
        elapsed = time.time() - start_time
        
        assert text_output is not None, "Output testo è None"
        assert json_output is not None, "Output JSON è None"
        
        print_success(f"get_crypto_forecasts (Prophet) completata in {elapsed:.2f}s")
        print_info("\nOutput testo (primi 200 caratteri):")
        print(text_output[:200] + "..." if len(text_output) > 200 else text_output)
        
        return True
    except Exception as e:
        print_error(f"Errore get_crypto_forecasts (Prophet): {e}")
        import traceback
        traceback.print_exc()
        return False


def test_format_forecast_text():
    """Test formattazione testo previsioni con dati reali"""
    print_test("Formattazione testo previsioni (dati reali)")
    
    if not USE_REAL_DATA:
        print_warning("Test saltato (USE_REAL_DATA=False)")
        return "SKIPPED"
    
    try:
        # Recupera previsioni reali
        try:
            forecaster = HybridForecaster(testnet=TESTNET)
        except ImportError as e:
            if "hyperliquid" in str(e).lower():
                print_warning("Hyperliquid non disponibile, test saltato")
                return "SKIPPED"
            raise
        
        # Esegui previsioni reali per almeno un ticker
        ticker = TEST_TICKERS[0]
        interval = TEST_INTERVALS[0]
        
        print_info(f"Esecuzione previsione reale per {ticker} {interval}...")
        result = forecaster.forecast(ticker, interval)
        
        if result is None or result.get('forecast_price') is None:
            print_error("Previsione reale fallita")
            return False
        
        # Crea lista di risultati reali per testare la formattazione
        test_results = [result]
        
        # Se possibile, aggiungi un secondo risultato
        if len(TEST_TICKERS) > 1:
            try:
                result2 = forecaster.forecast(TEST_TICKERS[1], TEST_INTERVALS[-1])
                if result2 and result2.get('forecast_price') is not None:
                    test_results.append(result2)
            except:
                pass  # Continua con un solo risultato se il secondo fallisce
        
        print_success(f"Recuperate {len(test_results)} previsioni reali")
        for r in test_results:
            print_info(f"  {r.get('symbol')} {r.get('interval')}: ${r.get('forecast_price')} ({r.get('pct_change'):+.2f}%)")
        
        # Test formattazione
        formatted = _format_forecast_text(test_results)
        
        assert formatted is not None, "Output formattato è None"
        assert "| Asset |" in formatted, "Header tabella mancante"
        assert "Timeframe" in formatted, "Header 'Timeframe' mancante"
        assert "Forecast Price" in formatted, "Header 'Forecast Price' mancante"
        assert "% Change" in formatted, "Header '% Change' mancante"
        assert "Model" in formatted, "Header 'Model' mancante"
        
        # Verifica che i dati reali siano presenti
        for r in test_results:
            symbol = r.get('symbol', '')
            assert symbol in formatted, f"Dati {symbol} mancanti nella formattazione"
        
        print_success("Formattazione testo corretta")
        print_info("\nOutput formattato:")
        print(formatted)
        
        # Verifica struttura tabella
        lines = formatted.split('\n')
        assert len(lines) >= 3, "Tabella troppo corta (manca header o dati)"
        assert lines[0].startswith('|'), "Prima riga non è una riga di tabella"
        assert '---' in lines[1] or '---' in lines[0], "Separatore tabella mancante"
        
        print_success("Struttura tabella valida")
        
        return True
    except Exception as e:
        print_error(f"Errore formattazione: {e}")
        import traceback
        traceback.print_exc()
        return False


# -------------------------------------------------------------------
#                    MAIN TEST RUNNER
# -------------------------------------------------------------------
def run_all_tests():
    """Esegue tutti i test"""
    print_section("TEST SUITE FORECASTER")
    print(f"Testnet: {TESTNET}")
    print(f"Use Real Data: {USE_REAL_DATA}")
    print(f"Tickers: {TEST_TICKERS}")
    print(f"Intervals: {TEST_INTERVALS}")
    
    tests = [
        ("Import Librerie", test_imports),
        ("Init HybridForecaster", test_hybrid_forecaster_init),
        ("Init HyperliquidForecaster", test_hyperliquid_forecaster_init),
        ("Fetch Candles", test_fetch_candles),
        ("ARIMA Training", test_arima_training),
        ("LSTM Training", test_lstm_training),
        ("Hybrid Forecast", test_hybrid_forecast),
        ("Forecast Many", test_forecast_many),
        ("Prophet Forecast", test_prophet_forecast),
        ("Format Forecast Text", test_format_forecast_text),
        ("get_crypto_forecasts (Hybrid)", test_get_crypto_forecasts_hybrid),
        ("get_crypto_forecasts (Prophet)", test_get_crypto_forecasts_prophet),
    ]
    
    results = []
    start_time = time.time()
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            # Se il risultato è "SKIPPED", traccia come saltato
            if result == "SKIPPED":
                results.append((test_name, True, "skipped"))
            elif result is True:
                results.append((test_name, True, "executed"))
            else:
                results.append((test_name, False, "failed"))
        except Exception as e:
            print_error(f"Test '{test_name}' ha sollevato un'eccezione: {e}")
            results.append((test_name, False, "failed"))
    
    elapsed = time.time() - start_time
    
    # Riepilogo
    print_section("RIEPILOGO TEST")
    
    passed = sum(1 for _, result, status in results if result and status == "executed")
    skipped = sum(1 for _, result, status in results if status == "skipped")
    failed = sum(1 for _, result, status in results if not result or status == "failed")
    total = len(results)
    
    # Mostra ogni test con il suo stato
    for test_name, result, status in results:
        if status == "skipped":
            print(f"⏭️  SKIP - {test_name} (librerie mancanti)")
        elif not result or status == "failed":
            print(f"❌ FAIL - {test_name}")
        else:
            print(f"✅ PASS - {test_name}")
    
    print(f"\n📊 Statistiche:")
    print(f"  Totale test: {total}")
    print(f"  ✅ Eseguiti e passati: {passed}")
    print(f"  ⏭️  Saltati: {skipped}")
    print(f"  ❌ Falliti: {failed}")
    print(f"  ⏱️  Tempo totale: {elapsed:.2f}s")
    
    # Verifica disponibilità librerie
    print(f"\n📦 Librerie disponibili:")
    print(f"  {'✅' if ARIMA_AVAILABLE else '❌'} statsmodels (ARIMA)")
    print(f"  {'✅' if TORCH_AVAILABLE else '❌'} torch (LSTM)")
    try:
        from prophet import Prophet
        print(f"  ✅ prophet")
    except:
        print(f"  ❌ prophet")
    try:
        from hyperliquid.info import Info
        print(f"  ✅ hyperliquid-python-sdk")
    except:
        print(f"  ❌ hyperliquid-python-sdk")
    
    if failed == 0:
        if passed == total:
            print_success("\n🎉 Tutti i test sono passati!")
        else:
            print_warning(f"\n⚠️  {total - passed} test saltati (librerie mancanti)")
            print_info("Installa le librerie mancanti per eseguire tutti i test:")
            if not ARIMA_AVAILABLE:
                print_info("  pip install statsmodels")
            if not TORCH_AVAILABLE:
                print_info("  pip install torch")
            try:
                from prophet import Prophet
            except:
                print_info("  pip install prophet")
            try:
                from hyperliquid.info import Info
            except:
                print_info("  pip install hyperliquid-python-sdk")
    else:
        print_warning(f"\n⚠️  {failed} test falliti")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

