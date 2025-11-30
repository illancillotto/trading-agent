import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import { Toaster } from 'react-hot-toast'
import { ModelSelector } from './components/ModelSelector'

function App() {
  return (
    <div className="h-screen flex flex-col">
      <header className="border-b border-border p-4">
        <div className="container mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">Trading Agent</h1>
          <ModelSelector />
        </div>
      </header>
      <main className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground">Frontend coming soon...</p>
        </div>
      </main>
      <Toaster position="top-right" />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Toaster position="top-right" />
    <App />
  </React.StrictMode>,
)
