# Telegram Instant View Setup Guide

## Overview

Telegram Instant View permette di visualizzare contenuti web in un formato nativo, veloce e ottimizzato direttamente in Telegram senza aprire il browser.

## Prerequisiti

1. ✅ Backend pubblicamente accessibile (es. Railway, VPS con dominio)
2. ✅ HTTPS configurato (obbligatorio per Instant View)
3. ✅ Variabile ambiente `PUBLIC_BASE_URL` configurata

## Step 1: Verifica Endpoint

Testa che l'endpoint funzioni:
```bash
# Sostituisci con il tuo dominio e trade_id reale
curl https://trading-dashboard.up.railway.app/trade-view/1
```

Dovresti ricevere HTML completo.

## Step 2: Crea Template Instant View

1. **Vai su**: https://instantview.telegram.org/
2. **Login** con il tuo account Telegram
3. **Clicca** "My Templates" → "Create new template"
4. **Inserisci** il tuo URL base: `https://trading-dashboard.up.railway.app/trade-view/`
5. **Incolla** il template sotto nella sezione "Template"

### Template Instant View:
```xpath
# Trading Agent - Instant View Template v1.0

# Required for article
~version: "2.1"

# Define source page elements
body: //body

# Title
title: //h1
subtitle: //div[@class="subtitle"]

# Article metadata
published_date: //meta[@property="article:published_time"]/@content

# Cover (optional - puoi aggiungere un'immagine)
# cover: //div[@class="header"]

# Main content sections
@json_to_text
@split_parent

# All metric cards
@append_after(//body): //div[@class="metric-card"]

# All sections
@append_after(//body): //div[@class="section"]

# Chart
@append_after(//body): //div[@class="chart-placeholder"]

# Footer
@append_after(//body): //footer

# Rimuovi elementi non necessari
@remove: //style
@remove: //script

# Format links
<link>: $@/<a>

# Format emphasis
<b>: //strong
<i>: //em
```

6. **Clicca** "Check" per validare il template
7. **Test** con un URL reale: `https://your-domain.com/trade-view/123`
8. **Submit** per approvazione Telegram (di solito approva in 24-48h)

## Step 3: Test Instant View

Mentre il template è in revisione, puoi testarlo:

1. Apri Telegram
2. Invia a te stesso (Saved Messages) il link: `https://your-domain.com/trade-view/1`
3. Clicca sul link
4. Dovrebbe apparire una preview con bottone "Instant View"
5. Clicca "Instant View" per vedere il rendering

**Nota**: Se il template non è ancora approvato, vedrai la versione web standard. Una volta approvato, tutti i link si apriranno automaticamente in Instant View.

## Step 4: Configura Environment Variables
```bash
# .env file
PUBLIC_BASE_URL=https://trading-dashboard.up.railway.app

# Oppure in Railway:
# Settings → Variables → Add Variable
# KEY: PUBLIC_BASE_URL
# VALUE: https://trading-dashboard.up.railway.app
```

## Step 5: Test Completo

1. **Avvia backend** con URL pubblico configurato
2. **Esegui un trade** (o usa dati esistenti)
3. **Controlla** che arrivi notifica Telegram con link
4. **Clicca** sul link "📊 View Full Details"
5. **Verifica** che si apra Instant View con:
   - ✅ Header colorato (verde per long, rosso per short)
   - ✅ Metriche P&L, entry, size, duration
   - ✅ Dettagli trade completi
   - ✅ Contesto AI (confidence, reasoning, indicators)
   - ✅ Chart placeholder
   - ✅ Footer con link dashboard

## Troubleshooting

### Link non genera Instant View

**Problema**: Link si apre nel browser anziché Instant View
- **Causa**: Template non ancora approvato o errore nel template
- **Soluzione**:
  - Verifica stato approvazione su https://instantview.telegram.org/
  - Controlla che URL sia HTTPS
  - Test template con checker integrato

### HTML non si carica

**Problema**: 404 o 500 error quando clicco link
- **Causa**: Trade ID non esiste o errore backend
- **Soluzione**:
  - Verifica che trade esista: `curl https://your-domain.com/trade-view-test/1`
  - Controlla logs backend per errori
  - Verifica database ha dati trade

### Template non valida

**Problema**: Instant View checker dice "Invalid template"
- **Soluzione**:
  - Usa template fornito sopra (già testato)
  - Verifica indentazione (no tab, usa spazi)
  - Segui documentazione: https://instantview.telegram.org/docs

### Notifiche non includono link

**Problema**: Notifica arriva ma senza link
- **Causa**: `PUBLIC_BASE_URL` non configurato o notifications.py non aggiornato
- **Soluzione**:
  - Verifica env: `echo $PUBLIC_BASE_URL`
  - Controlla modifiche a notifications.py siano applicate
  - Riavvia backend

## Advanced: Custom Styling

Per personalizzare ulteriormente l'Instant View:

1. **Modifica** `trade_view_generator.py` template HTML
2. **Mantieni** struttura compatibile con Instant View:
   - Usa tag semantici: `<h1>`, `<h2>`, `<p>`, `<div>`
   - Evita JavaScript
   - Limita CSS inline
3. **Testa** modifiche con checker Instant View
4. **Deploy** e verifica rendering

## References

- [Instant View Docs](https://instantview.telegram.org/docs)
- [Template Format Reference](https://instantview.telegram.org/docs#template-format)
- [XPath Reference](https://www.w3schools.com/xml/xpath_syntax.asp)

---

**Last Updated**: {{ current_date }}
**Version**: 1.0
