import { useEffect, useState } from 'react'

interface CurrentModel {
    id: string
    name: string
    model_id: string
    provider: string
    available: boolean
}

// Use relative URLs in development (via Vite proxy) or absolute URL if VITE_API_URL is set
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export function ModelSelector() {
    const [currentModel, setCurrentModel] = useState<CurrentModel | null>(null)
    const [scalpingEnabled, setScalpingEnabled] = useState(false)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        fetchData()
    }, [])

    const fetchData = async () => {
        try {
            const [modelRes, configRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/models/current`),
                fetch(`${API_BASE_URL}/api/config`)
            ])

            if (modelRes.ok) {
                const modelData = await modelRes.json()
                setCurrentModel(modelData)
            }

            if (configRes.ok) {
                const configData = await configRes.json()
                setScalpingEnabled(configData.trend_confirmation?.allow_scalping || false)
            }
        } catch (error) {
            console.error('Error fetching data:', error)
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground">
                <span>Caricamento modello...</span>
            </div>
        )
    }

    if (!currentModel) {
        return (
            <div className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground">
                <span>Nessun modello disponibile</span>
            </div>
        )
    }

    return (
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3">
            <span className="text-xs sm:text-sm text-muted-foreground hidden sm:inline">Modello:</span>
            <div className="flex items-center gap-2 px-2.5 sm:px-3 py-1.5 text-xs sm:text-sm bg-background border border-input rounded-md w-full sm:w-auto">
                <span className="font-medium">{currentModel.name}</span>
                <span className="text-[10px] sm:text-xs text-muted-foreground">
                    ({currentModel.provider})
                </span>
            </div>
            <div className="flex items-center gap-1 text-[10px] sm:text-xs text-muted-foreground">
                <span className="px-2 py-1 bg-muted rounded-sm truncate max-w-[200px] sm:max-w-none">
                    {currentModel.model_id}
                </span>
            </div>
            {scalpingEnabled && (
                <div className="flex items-center px-2 py-1 bg-amber-50 border border-amber-200 rounded text-[10px] sm:text-xs text-amber-700 font-medium animate-pulse">
                    ⚡ Scalping
                </div>
            )}
        </div>
    )
}
