import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { detectLocal } from './mode'
import './index.css'

// Der lokale Modus wird vor dem ersten Rendern über /api/meta erkannt; danach gibt es keine Auth-Aufrufe.
void detectLocal().then((local) => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App local={local} />
    </StrictMode>
  )
})
