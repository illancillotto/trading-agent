"""
Trading Agent - Decisioni AI con supporto multi-modello
"""
import json
import logging
import time
from typing import Optional, Dict, Any

from model_manager import get_model_manager
from token_tracker import get_token_tracker

logger = logging.getLogger(__name__)

# Costanti
MAX_RETRIES = 3
TIMEOUT_SECONDS = 60

# JSON Schema per structured output (NOF1.ai Standards)
TRADE_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["open", "close", "hold"],
            "description": "Trading action to take"
        },
        "symbol": {
            "type": "string",
            "description": "Cryptocurrency symbol (e.g., BTC, ETH, SOL)"
        },
        "direction": {
            "type": "string",
            "enum": ["long", "short"],
            "description": "Trade direction"
        },
        "target_portion_of_balance": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 0.30,
            "description": "Portion of available balance to use (max 30%)"
        },
        "leverage": {
            "type": "integer",
            "minimum": 1,
            "maximum": 8,
            "description": "Leverage multiplier (1-8x based on confidence)"
        },
        "stop_loss_pct": {
            "type": "number",
            "minimum": 1.5,
            "maximum": 5.0,
            "description": "Stop loss percentage (1.5-5.0%)"
        },
        "take_profit_pct": {
            "type": "number",
            "minimum": 2.25,
            "maximum": 50.0,
            "description": "Take profit percentage (must be >= 1.5x stop_loss)"
        },
        "invalidation_condition": {
            "type": "string",
            "minLength": 10,
            "maxLength": 200,
            "description": "Specific condition that invalidates the trade thesis"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence level in the trade (0.0-1.0)"
        },
        "risk_usd": {
            "type": "number",
            "minimum": 0.0,
            "description": "Dollar amount at risk (calculated as: portion * balance * sl_pct * leverage)"
        },
        "reason": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500,
            "description": "Detailed explanation of the decision"
        }
    },
    "required": [
        "operation",
        "symbol",
        "direction",
        "target_portion_of_balance",
        "leverage",
        "stop_loss_pct",
        "take_profit_pct",
        "invalidation_condition",
        "confidence",
        "risk_usd",
        "reason"
    ],
    "additionalProperties": False
}


def previsione_trading_agent(
    prompt: str,
    max_retries: int = MAX_RETRIES,
    model_key: Optional[str] = None,
    cycle_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Chiama il modello AI selezionato per ottenere decisioni di trading strutturate.

    Args:
        prompt: System prompt con dati di mercato e portfolio
        max_retries: Numero massimo di tentativi
        model_key: Chiave del modello da usare (None = modello corrente)

    Returns:
        Dict con la decisione di trading

    Raises:
        RuntimeError: Se tutti i tentativi falliscono
    """
    model_manager = get_model_manager()
    
    # Determina il modello da usare
    if model_key:
        if not model_manager.is_model_available(model_key):
            logger.error(f"❌ Modello {model_key} non disponibile")
            model_key = None
    
    if not model_key:
        model_key = model_manager.get_current_model()
    
    model_config = model_manager.get_model_config(model_key)
    client = model_manager.get_client(model_key)
    
    if not client or not model_config:
        logger.error(f"❌ Client o configurazione non disponibile per {model_key}")
        raise RuntimeError(f"Modello {model_key} non disponibile")
    
    # Lista di modelli fallback (escludendo quello corrente)
    fallback_models = [m for m in model_manager.get_available_models() 
                      if m["id"] != model_key and m["available"]]
    
    last_error = None

    for attempt in range(max_retries):
        try:
            # Usa modello corrente per i primi tentativi, poi fallback
            if attempt == 0:
                current_model_key = model_key
            elif attempt < len(fallback_models) + 1:
                current_model_key = fallback_models[attempt - 1]["id"]
            else:
                current_model_key = model_key  # Ultimo tentativo con modello originale
            
            current_config = model_manager.get_model_config(current_model_key)
            current_client = model_manager.get_client(current_model_key)
            
            if not current_client or not current_config:
                continue
            
            logger.info(
                f"🤖 API call (attempt {attempt + 1}/{max_retries}, "
                f"model: {current_config.name} ({current_config.model_id}))"
            )

            # Misura tempo di risposta per tracking
            start_time = time.time()

            # Prepare system prompt based on model capabilities
            if current_config.supports_json_schema:
                # For models with json_schema, the prompt can be simpler
                system_content = "You are a professional trading AI. Analyze the data and respond ONLY with valid JSON according to the required schema."
            else:
                # For models without json_schema (e.g. DeepSeek), include the schema in the prompt
                system_content = """You are a professional trading AI. Analyze the data and respond EXCLUSIVELY with a valid JSON in this exact format:

{
  "operation": "open|close|hold",
  "symbol": "COIN_SYMBOL",
  "direction": "long|short",
  "target_portion_of_balance": 0.15,
  "leverage": 3,
  "stop_loss_pct": 2.5,
  "take_profit_pct": 5.0,
  "invalidation_condition": "Specific, observable condition that voids this trade thesis",
  "confidence": 0.65,
  "risk_usd": 25.0,
  "reason": "Detailed explanation of the decision"
}

IMPORTANT:
- operation must be one of: "open", "close", "hold"
- symbol must be the ticker of the analyzed coin (e.g. "BTC", "ETH", "SOL")
- direction must be "long" or "short"
- target_portion_of_balance: number between 0.0 and 0.30 (max 30%)
- leverage: integer between 1 and 8 (based on confidence)
- stop_loss_pct: number between 1.5 and 5.0
- take_profit_pct: number between 2.25 and 50.0 (must be >= 1.5x stop_loss_pct)
- invalidation_condition: string (10-200 chars), specific condition that proves you were wrong
- confidence: number between 0.0 and 1.0
- risk_usd: calculated dollar risk (portion × balance × sl_pct × leverage)
- reason: string (10-500 chars), detailed explanation
- Respond ONLY with the JSON, without additional text."""

            # Prepara i parametri della richiesta
            request_params = {
                "model": current_config.model_id,
                "messages": [
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # Bassa per decisioni più consistenti
                "timeout": TIMEOUT_SECONDS
            }
            
            # Usa il parametro corretto per limitare i token di output
            # GPT-5.1 richiede max_completion_tokens, altri modelli usano max_tokens
            if current_config.use_max_completion_tokens:
                request_params["max_completion_tokens"] = 1000
            else:
                request_params["max_tokens"] = 1000
            
            # Aggiungi formato JSON appropriato
            if current_config.supports_json_schema:
                # Usa json_schema per modelli che lo supportano (OpenAI)
                request_params["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "trade_decision",
                        "strict": True,
                        "schema": TRADE_DECISION_SCHEMA
                    }
                }
            else:
                # Usa json_object per modelli che non supportano json_schema (es. DeepSeek)
                request_params["response_format"] = {"type": "json_object"}
            
            response = current_client.chat.completions.create(**request_params)

            # Calcola tempo di risposta
            response_time_ms = int((time.time() - start_time) * 1000)

            # Traccia utilizzo token
            try:
                tracker = get_token_tracker()
                usage = response.usage
                
                # Estrai simbolo dal prompt se possibile (per ticker)
                ticker = None
                if "symbol" in prompt.lower():
                    # Cerca simboli comuni nel prompt
                    for sym in ["BTC", "ETH", "SOL"]:
                        if sym in prompt:
                            ticker = sym
                            break
                
                tracker.track_usage(
                    model=current_config.model_id,
                    input_tokens=usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0,
                    output_tokens=usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0,
                    purpose="Trading Decision",
                    ticker=ticker,
                    cycle_id=cycle_id,
                    response_time_ms=response_time_ms
                )
            except Exception as e:
                # Non bloccare il flusso se il tracking fallisce
                logger.warning(f"⚠️ Errore tracking token: {e}")

            # Estrai risposta
            response_text = response.choices[0].message.content

            if not response_text:
                raise ValueError(f"Risposta vuota da {current_config.name}")

            # Parse JSON
            decision = json.loads(response_text)

            # Validazione aggiuntiva
            _validate_decision(decision)

            logger.info(
                f"✅ Decisione ({current_config.name}): {decision['operation']} {decision['symbol']} "
                f"{decision['direction']} (confidence: {decision['confidence']:.1%})"
            )
            
            # Aggiungi info sul modello usato alla risposta
            decision["_model_used"] = current_model_key
            decision["_model_name"] = current_config.name

            return decision

        except json.JSONDecodeError as e:
            last_error = e
            logger.error(f"❌ JSON parse error (attempt {attempt + 1}): {e}")

        except Exception as e:
            last_error = e
            logger.error(f"❌ API error (attempt {attempt + 1}): {e}")

        # Exponential backoff
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            logger.info(f"⏳ Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    # Tutti i tentativi falliti - ritorna decisione di sicurezza
    logger.error(f"❌ Tutti i {max_retries} tentativi falliti. Ultimo errore: {last_error}")
    logger.warning("⚠️ Usando fallback HOLD neutrale")

    return {
        "operation": "hold",
        "symbol": "BTC",
        "direction": "long",  # Keep for schema compatibility, but operation is HOLD so it won't execute
        "target_portion_of_balance": 0.0,
        "leverage": 1,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 4.0,
        "invalidation_condition": "N/A - Fallback decision due to API error",
        "confidence": 0.0,
        "risk_usd": 0.0,
        "reason": f"Fallback a HOLD per errore API: {str(last_error)[:100]}",
        "_fallback": True  # Flag to indicate this is a fallback response
    }


def _validate_decision(decision: Dict[str, Any]) -> None:
    """
    Validazione aggiuntiva della decisione di trading.

    Raises:
        ValueError: Se la decisione non è valida
    """

    # Verifica R:R ratio
    sl_pct = decision.get('stop_loss_pct', 0)
    tp_pct = decision.get('take_profit_pct', 0)

    if sl_pct > 0:
        rr_ratio = tp_pct / sl_pct
        if rr_ratio < 1.0:
            logger.warning(f"⚠️ R:R ratio basso: {rr_ratio:.2f} (TP: {tp_pct}%, SL: {sl_pct}%)")

    # Verifica confidence
    confidence = decision.get('confidence', 0)
    if confidence < 0.3:
        logger.warning(f"⚠️ Confidence bassa: {confidence:.1%}")

    # Verifica position size con leva
    portion = decision.get('target_portion_of_balance', 0)
    leverage = decision.get('leverage', 1)
    effective_exposure = portion * leverage

    if effective_exposure > 0.5:
        logger.warning(f"⚠️ Esposizione elevata: {effective_exposure:.1%} (portion={portion:.1%}, leva={leverage}x)")


def validate_trade_decision(decision: Dict, account_balance: float) -> tuple[bool, str]:
    """
    Validate trade decision against NOF1.ai rules.

    Args:
        decision: Trade decision dict
        account_balance: Current account balance in USD

    Returns:
        (is_valid, error_message) tuple
    """
    from typing import Tuple
    errors = []

    # Check R:R ratio (minimum 1.5:1)
    sl = decision.get('stop_loss_pct', 0)
    tp = decision.get('take_profit_pct', 0)
    if sl > 0 and tp < (sl * 1.5):
        rr = tp / sl if sl > 0 else 0
        errors.append(f"R:R ratio too low: {rr:.2f}x (min 1.5x required)")

    # Check invalidation condition
    inv_cond = decision.get('invalidation_condition', '')
    if not inv_cond or len(inv_cond) < 10:
        errors.append("Missing or too short invalidation_condition (min 10 chars)")

    # Check confidence threshold for opening positions
    if decision.get('operation') == 'open':
        conf = decision.get('confidence', 0)
        if conf < 0.5:
            errors.append(f"Confidence too low to open: {conf:.2f} (min 0.5 required)")

    # Check risk_usd doesn't exceed 3% of account
    risk_usd = decision.get('risk_usd', 0)
    max_risk = account_balance * 0.03  # 3% max risk
    if risk_usd > max_risk:
        errors.append(f"Risk ${risk_usd:.2f} exceeds 3% of account (max ${max_risk:.2f})")

    # Check leverage based on confidence
    leverage = decision.get('leverage', 1)
    confidence = decision.get('confidence', 0)
    max_lev_for_conf = _get_max_leverage_for_confidence(confidence)
    if leverage > max_lev_for_conf:
        errors.append(
            f"Leverage {leverage}x too high for confidence {confidence:.2f} "
            f"(max {max_lev_for_conf}x for this confidence level)"
        )

    # Check target_portion_of_balance
    portion = decision.get('target_portion_of_balance', 0)
    if portion > 0.30:
        errors.append(f"Position size {portion:.1%} exceeds 30% maximum")

    # Verify risk_usd calculation matches expected
    expected_risk = portion * account_balance * (sl / 100) * leverage
    if risk_usd > 0 and abs(risk_usd - expected_risk) / max(risk_usd, expected_risk, 1) > 0.1:  # 10% tolerance
        logger.warning(
            f"⚠️ risk_usd mismatch: provided={risk_usd:.2f}, "
            f"expected={expected_risk:.2f}"
        )

    if errors:
        return False, "; ".join(errors)
    return True, ""


def _get_max_leverage_for_confidence(confidence: float) -> int:
    """
    Get maximum allowed leverage based on confidence level (NOF1.ai standards).

    Args:
        confidence: Confidence level (0.0-1.0)

    Returns:
        Maximum leverage allowed
    """
    if confidence < 0.50:
        return 1  # Should not open, but if forced, minimum leverage
    elif confidence < 0.60:
        return 2  # Low conviction
    elif confidence < 0.70:
        return 4  # Moderate conviction
    elif confidence < 0.85:
        return 6  # High conviction
    else:
        return 8  # Very high conviction


# Funzione di test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_prompt = """
    Portfolio: Balance $1000, nessuna posizione aperta.

    BTC: $95000, RSI=45, MACD positivo, trend rialzista.
    Sentiment: Fear & Greed = 35 (Fear)

    Decidi se aprire una posizione.
    """

    result = previsione_trading_agent(test_prompt)
    print(f"\n📊 Risultato test:\n{json.dumps(result, indent=2)}")
