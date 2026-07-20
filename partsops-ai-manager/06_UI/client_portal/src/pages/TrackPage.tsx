import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

interface RequestView {
  request_id: string
  status: string
  customer_name?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  parts?: Array<{ name: string; quantity?: number; sale_price?: number; match_score?: number }>
  created_at?: string
  updated_at?: string
  erp_quotation_ref?: string
  erp_invoice_ref?: string
}

export function TrackPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [request, setRequest] = useState<RequestView | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    fetch(`/api/client/track/${token}`)
      .then(res => {
        if (!res.ok) throw new Error('Not found')
        return res.json()
      })
      .then(setRequest)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  const statusColors: Record<string, string> = {
    NEW: 'bg-blue-600',
    SENT_TO_CLIENT: 'bg-yellow-500',
    PAID: 'bg-green-600',
    CLIENT_REJECTED: 'bg-red-600',
    CLOSED: 'bg-gray-500',
    MANUAL_REVIEW: 'bg-purple-600',
  }

  if (loading) return <div className="p-4">Loading...</div>
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>
  if (!request) return <div className="p-4">Request not found</div>

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-gray-800 rounded-lg p-6 mb-4">
        <h2 className="text-2xl font-bold mb-2">Request {request.request_id}</h2>
        <div className="flex items-center gap-2 mb-4">
          <span className={`px-3 py-1 rounded-full ${statusColors[request.status] || 'bg-gray-500'}`}>
            {request.status}
          </span>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-gray-400">Customer</div>
            <div>{request.customer_name || 'N/A'}</div>
          </div>
          <div>
            <div className="text-gray-400">Vehicle</div>
            <div>{request.vehicle_make} {request.vehicle_model} {request.vehicle_year || ''}</div>
          </div>
        </div>
      </div>

      {request.parts && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-bold mb-4">Parts</h3>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="pb-2">Name</th>
                <th className="pb-2">Qty</th>
                <th className="pb-2">Price</th>
                <th className="pb-2">Match</th>
              </tr>
            </thead>
            <tbody>
              {request.parts.map((p, i) => (
                <tr key={i} className="border-b border-gray-800">
                  <td className="py-2">{p.name}</td>
                  <td>{p.quantity || 1}</td>
                  <td>${p.sale_price || 'N/A'}</td>
                  <td>{p.match_score ? `${Math.round(p.match_score)}%` : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex gap-4">
        {request.status === 'SENT_TO_CLIENT' && (
          <>
            <button onClick={() => navigate(`/offer/${token}/accept`)} className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded">
              Accept Offer
            </button>
            <button onClick={() => navigate(`/offer/${token}/reject`)} className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded">
              Reject Offer
            </button>
          </>
        )}
      </div>
    </div>
  )
}
