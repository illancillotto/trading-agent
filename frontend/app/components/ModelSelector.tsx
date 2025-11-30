import React, { useEffect, useState } from 'react'
import * as Select from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import toast from 'react-hot-toast'

interface Model {
  id: string
  name: string
  model_id: string
  provider: string
  available: boolean
  supports_json_schema: boolean
  supports_reasoning: boolean
}

interface CurrentModel {
  id: string
  name: string
  model_id: string
  provider: string
  available: boolean
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function ModelSelector() {
  const [models, setModels] = useState<Model[]>([])
  const [currentModel, setCurrentModel] = useState<CurrentModel | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchModels()
    fetchCurrentModel()
  }, [])

  const fetchModels = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models`)
      if (!response.ok) throw new Error('Failed to fetch models')
      const data = await response.json()
      setModels(data)
    } catch (error) {
      console.error('Error fetching models:', error)
      toast.error('Errore nel caricamento dei modelli')
    } finally {
      setLoading(false)
    }
  }

  const fetchCurrentModel = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models/current`)
      if (!response.ok) throw new Error('Failed to fetch current model')
      const data = await response.json()
      setCurrentModel(data)
    } catch (error) {
      console.error('Error fetching current model:', error)
    }
  }

  const handleModelChange = async (modelId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models/current`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ model_id: modelId }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to set model')
      }

      const data = await response.json()
      setCurrentModel(data)
      toast.success(`Modello impostato su ${data.name}`)
    } catch (error) {
      console.error('Error setting model:', error)
      toast.error(error instanceof Error ? error.message : 'Errore nell\'impostazione del modello')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Caricamento modelli...</span>
      </div>
    )
  }

  const availableModels = models.filter(m => m.available)

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-muted-foreground">Modello:</span>
      <Select.Root
        value={currentModel?.id || ''}
        onValueChange={handleModelChange}
        disabled={availableModels.length === 0}
      >
        <Select.Trigger className="inline-flex items-center justify-between gap-2 px-3 py-1.5 text-sm bg-background border border-input hover:bg-accent hover:text-accent-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed min-w-[180px]">
          <Select.Value placeholder="Seleziona modello">
            {currentModel ? (
              <span className="flex items-center gap-2">
                <span>{currentModel.name}</span>
                <span className="text-xs text-muted-foreground">
                  ({currentModel.provider})
                </span>
              </span>
            ) : (
              'Nessun modello'
            )}
          </Select.Value>
          <Select.Icon>
            <ChevronDown className="h-4 w-4" />
          </Select.Icon>
        </Select.Trigger>

        <Select.Portal>
          <Select.Content className="overflow-hidden bg-popover border border-border shadow-lg min-w-[200px]">
            <Select.Viewport className="p-1">
              {availableModels.length === 0 ? (
                <Select.Item
                  value="none"
                  disabled
                  className="px-3 py-2 text-sm text-muted-foreground cursor-not-allowed"
                >
                  Nessun modello disponibile
                </Select.Item>
              ) : (
                availableModels.map((model) => (
                  <Select.Item
                    key={model.id}
                    value={model.id}
                    className="relative flex items-center px-3 py-2 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none data-[disabled]:opacity-50 data-[disabled]:pointer-events-none"
                  >
                    <Select.ItemText>
                      <div className="flex items-center justify-between w-full">
                        <div className="flex flex-col">
                          <span className="font-medium">{model.name}</span>
                          <span className="text-xs text-muted-foreground">
                            {model.provider} • {model.model_id}
                          </span>
                        </div>
                        {model.id === currentModel?.id && (
                          <Check className="h-4 w-4 text-primary" />
                        )}
                      </div>
                    </Select.ItemText>
                    <Select.ItemIndicator className="absolute left-0 w-6 inline-flex items-center justify-center">
                      <Check className="h-4 w-4" />
                    </Select.ItemIndicator>
                  </Select.Item>
                ))
              )}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
      
      {currentModel && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span className="px-2 py-1 bg-muted rounded-sm">
            {currentModel.model_id}
          </span>
        </div>
      )}
    </div>
  )
}

