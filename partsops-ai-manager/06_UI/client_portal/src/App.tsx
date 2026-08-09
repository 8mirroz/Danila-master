import React from 'react'
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom'
import { TrackPage } from './pages/TrackPage'
import { OfferPage } from './pages/OfferPage'

function HomePage() {
  return (
    <div className="max-w-lg mx-auto mt-10 rounded-xl border border-gray-700 bg-gray-800 p-6 text-center">
      <h2 className="text-lg font-bold text-white">PartsOps Client Portal</h2>
      <p className="mt-2 text-sm text-gray-400 leading-relaxed">
        Это публичный трекинг коммерческих предложений. Откройте персональную ссылку из письма или
        Telegram (<code className="text-gray-300">/track/&lt;token&gt;</code>). Демо-данные и
        вымышленные пакеты поставки не показываются.
      </p>
      <p className="mt-4 text-xs text-gray-500">
        Нужна помощь? Свяжитесь с менеджером, который отправил предложение.
      </p>
    </div>
  )
}

function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="bg-gray-800 p-4 border-b border-gray-700">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <Link to="/" className="text-xl font-bold hover:text-gray-200">
            PartsOps Client Portal
          </Link>
          <span className="text-[10px] uppercase tracking-wide text-gray-500">Public · no margin</span>
        </div>
      </header>
      <div className="p-4">
        <Routes>
          <Route path="/track/:token" element={<TrackPage />} />
          <Route path="/offer/:token" element={<OfferPage />} />
          <Route path="/offer/:token/accept" element={<OfferPage action="accept" />} />
          <Route path="/offer/:token/reject" element={<OfferPage action="reject" />} />
          <Route path="/" element={<HomePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  )
}

export default App
