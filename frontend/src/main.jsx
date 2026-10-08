import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AuthProvider } from './context/AuthContext.jsx'
import './index.css'

// AuthProvider wraps the ENTIRE app so every component can call useAuth()
// to read the current session, no matter how deeply nested it is.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>
)
