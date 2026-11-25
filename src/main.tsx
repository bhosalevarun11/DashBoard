import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

if (typeof window !== 'undefined') {
  console.log(
    '%cWARNING: STOP!',
    'color: red; font-size: 32px; font-weight: bold;'
  )
  console.log(
    '%cThis browser console feature is intended for developers. If someone told you to copy and paste code here to unlock a feature or access an account, it is a scam and will compromise your account.',
    'font-size: 14px; color: #444;'
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
