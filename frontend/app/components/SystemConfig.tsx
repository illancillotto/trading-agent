import { useEffect, useState } from 'react'

interface SystemConfig {
    trading: {
        testnet: boolean
        tickers: string[]
        cycle_interval_minutes: number
    }
    cycles: {
        trading_cycle_minutes: number
        sentiment_api_minutes: number
        health_check_minutes: number
    }
    coin_screener: {
        enabled: boolean
        top_n_coins: number
        rebalance_day: string
        fallback_tickers: string[]
    }
    trend_confirmation: {
        enabled: boolean
        min_confidence: number
        allow_scalping: boolean
    }
    risk_management: {
        max_daily_loss_usd: number
        max_daily_loss_pct: number
        max_position_pct: number
        default_stop_loss_pct: number
        default_take_profit_pct: number
    }
}

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export function SystemConfig() {
    const [config, setConfig] = useState<SystemConfig | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchConfig = async () => {
        setLoading(true)
        setError(null)
        try {
            const res = await fetch(`${API_BASE_URL}/api/config`)
            if (!res.ok) throw new Error('Failed to fetch config')
            setConfig(await res.json())
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Errore sconosciuto')
            console.error('Error fetching config:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchConfig()
        // Refresh ogni 5 minuti (la config cambia raramente)
        const interval = setInterval(fetchConfig, 300000)
        return () => clearInterval(interval)
    }, [])

    if (loading) {
        return (
            <div className="p-4 text-center text-gray-500 text-xs">Caricamento configurazione...</div>
        )
    }

    if (error || !config) {
        return (
            <div className="p-4 text-center text-red-500 text-xs">
                {error || 'Configurazione non disponibile'}
                <button onClick={fetchConfig} className="ml-2 text-blue-500 hover:underline">Riprova</button>
            </div>
        )
    }

    return (
        <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold text-gray-800 flex items-center gap-2">
                    <span className="text-xl">⚙️</span>
                    Configurazione Sistema
                </h3>
                <button
                    onClick={fetchConfig}
                    className="p-1 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 transition-colors"
                    title="Aggiorna configurazione"
                >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                </button>
            </div>

            <div className="space-y-4">
                {/* Trading Info */}
                <div className="border-b pb-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">📊 Trading</h4>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                            <span className="text-gray-500">Network:</span>
                            <span className="ml-2 font-mono">{config.trading.testnet ? '🧪 TESTNET' : '🌐 MAINNET'}</span>
                        </div>
                        <div>
                            <span className="text-gray-500">Tickers (Fallback):</span>
                            <span className="ml-2">{config.trading.tickers.join(', ')}</span>
                        </div>
                    </div>
                </div>

                {/* Cycles Info */}
                <div className="border-b pb-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">⏱️ Cicli di Esecuzione</h4>
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                            <span className="text-gray-500">Trading Cycle:</span>
                            <span className="font-mono font-semibold">{config.cycles.trading_cycle_minutes} minuti</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-500">Sentiment API:</span>
                            <span className="font-mono font-semibold">{config.cycles.sentiment_api_minutes} minuti</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-500">Health Check:</span>
                            <span className="font-mono font-semibold">{config.cycles.health_check_minutes} minuti</span>
                        </div>
                    </div>
                </div>

                {/* Coin Screener Info */}
                <div className="border-b pb-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">🔍 Coin Screener</h4>
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                            <span className="text-gray-500">Stato:</span>
                            <span className={`font-semibold ${config.coin_screener.enabled ? 'text-green-600' : 'text-red-600'}`}>
                                {config.coin_screener.enabled ? '✅ Abilitato' : '❌ Disabilitato'}
                            </span>
                        </div>
                        {config.coin_screener.enabled && (
                            <>
                                <div className="flex justify-between">
                                    <span className="text-gray-500">Top N Coins:</span>
                                    <span className="font-mono font-semibold">{config.coin_screener.top_n_coins}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-500">Rebalance:</span>
                                    <span className="font-semibold">Ogni {config.coin_screener.rebalance_day.charAt(0).toUpperCase() + config.coin_screener.rebalance_day.slice(1)} 00:00 UTC</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-500">Update Scores:</span>
                                    <span className="font-semibold">Giornaliero</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-500">Fallback:</span>
                                    <span className="text-xs">{config.coin_screener.fallback_tickers.join(', ')}</span>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Trend Confirmation */}
                <div className="border-b pb-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">📈 Trend Confirmation</h4>
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                            <span className="text-gray-500">Stato:</span>
                            <span className={`font-semibold ${config.trend_confirmation.enabled ? 'text-green-600' : 'text-red-600'}`}>
                                {config.trend_confirmation.enabled ? '✅ Abilitato' : '❌ Disabilitato'}
                            </span>
                        </div>
                        {config.trend_confirmation.enabled && (
                            <>
                                <div className="flex justify-between">
                                    <span className="text-gray-500">Min Confidence:</span>
                                    <span className="font-mono font-semibold">{(config.trend_confirmation.min_confidence * 100).toFixed(0)}%</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-500">Scalping Mode:</span>
                                    <span className={`font-mono font-semibold ${config.trend_confirmation.allow_scalping ? 'text-amber-600' : 'text-gray-400'}`}>
                                        {config.trend_confirmation.allow_scalping ? '⚡ ON' : 'OFF'}
                                    </span>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Risk Management */}
                <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">🛡️ Risk Management</h4>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                            <span className="text-gray-500">Max Daily Loss:</span>
                            <span className="ml-1 font-mono">${config.risk_management.max_daily_loss_usd}</span>
                        </div>
                        <div>
                            <span className="text-gray-500">Max Position:</span>
                            <span className="ml-1 font-mono">{config.risk_management.max_position_pct}%</span>
                        </div>
                        <div>
                            <span className="text-gray-500">Stop Loss:</span>
                            <span className="ml-1 font-mono">{config.risk_management.default_stop_loss_pct}%</span>
                        </div>
                        <div>
                            <span className="text-gray-500">Take Profit:</span>
                            <span className="ml-1 font-mono">{config.risk_management.default_take_profit_pct}%</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

