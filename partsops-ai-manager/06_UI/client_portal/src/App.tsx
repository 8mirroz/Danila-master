import React from 'react'
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom'
import { TrackPage } from './pages/TrackPage'
import { OfferPage } from './pages/OfferPage'

function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="bg-gray-800 p-4 border-b border-gray-700">
        <h1 className="text-xl font-bold">PartsOps Client Portal</h1>
      </header>
      <div className="p-4">
        <Routes>
          <Route path="/track/:token" element={<TrackPage />} />
          <Route path="/offer/:token" element={<OfferPage />} />
          <Route path="/offer/:token/accept" element={<OfferPage action="accept" />} />
          <Route path="/offer/:token/reject" element={<OfferPage action="reject" />} />
          <Route path="/" element={<Navigate to="/track/default" />} />
        </Routes>
      </div>
    </div>
  )
}

export default App
