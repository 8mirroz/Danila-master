import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

interface LineItem {
  part_name: string
  sale_price: number
  match_score?: number
}

interface OfferView {
  request_id: string
  status: string
  parts?: LineItem[]
  erp_invoice_ref?: string
}

export function OfferPage({ action }: { action?: 'accept' | 'reject' }) {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [offer, setOffer] = useState<OfferView | null>(null)
  const [loading, setLoading] = useState(true)
  const [rejectReason, setRejectReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    fetch(`/api/client/track/${token}`)
      .then(res => {
        if (!res.ok) throw new Error('Not found')
        return res.json()
      })
      .then(setOffer)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  const handleAccept = async () => {
    const res = await fetch(`/api/client/track/${token}/accept`, { method: 'POST' })
    if (res.ok) navigate(`/track/${token}`)
  }

  const handleReject = async () => {
    const res = await fetch(`/api/client/track/${token}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: rejectReason })
    })
    if (res.ok) navigate(`/track/${token}`)
  }

  if (loading) return <div className="p-4">Loading...</div>
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>
  if (!offer) return <div className="p-4">Offer not found</div>

  if (action === 'accept') {
    return (
      <div className="max-w-xl mx-auto">
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">Confirm Acceptance</h2>
          <p className="mb-6">Are you sure you want to accept the offer for {offer.request_id}?</p>
          <div className="flex gap-4">
            <button onClick={handleAccept} className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded">
              Yes, Accept
            </button>
            <button onClick={() => navigate(-1)} className="bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded">
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (action === 'reject') {
    return (
      <div className="max-w-xl mx-auto">
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">Reject Offer</h2>
          <textarea
            className="w-full bg-gray-700 text-white p-3 rounded mb-4"
            rows={3}
            placeholder="Reason for rejection (optional)"
            value={rejectReason}
            onChange={e => setRejectReason(e.target.value)}
          />
          <div className="flex gap-4">
            <button onClick={handleReject} className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded">
              Confirm Rejection
            </button>
            <button onClick={() => navigate(-1)} className="bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded">
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-gray-800 rounded-lg p-6 mb-4">
        <h2 className="text-2xl font-bold mb-2">Your Offer</h2>
        <p className="text-gray-400">Request: {offer.request_id}</p>
        {offer.erp_invoice_ref && <p className="text-gray-400">Invoice: {offer.erp_invoice_ref}</p>}
      </div>

      {offer.parts && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-bold mb-4">Line Items</h3>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="pb-2">Part</th>
                <th className="pb-2">Price</th>
                <th className="pb-2">Match</th>
              </tr>
            </thead>
            <tbody>
              {offer.parts.map((p, i) => (
                <tr key={i} className="border-b border-gray-800">
                  <td className="py-2">{p.part_name}</td>
                  <td className="py-2 text-green-400 font-bold">${p.sale_price}</td>
                  <td>{p.match_score ? `${Math.round(p.match_score)}%` : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-6 flex gap-4">
        <button onClick={() => navigate(`/offer/${token}/accept`)} className="bg-green-600 hover:bg-green-700 px-6 py-3 rounded font-bold">
          Accept Offer
        </button>
        <button onClick={() => navigate(`/offer/${token}/reject`)} className="bg-red-600 hover:bg-red-700 px-6 py-3 rounded font-bold">
          Reject Offer
        </button>
      </div>
    </div>
  )
}
