import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

interface RequestView {
  request_id: string
  status: string
  customer_name?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number | string
  parts?: Array<{ name: string; quantity?: number; sale_price?: number; match_score?: number }>
  created_at?: string
  updated_at?: string
  erp_quotation_ref?: string
  erp_invoice_ref?: string
}

function formatRub(value: number | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toLocaleString('ru-RU')} ₽`
}

export function TrackPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [request, setRequest] = useState<RequestView | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token || token === 'default') {
      setError('Откройте персональную ссылку трекинга из письма или Telegram. Маршрут /track/default не содержит данных.')
      setLoading(false)
      return
    }
    fetch(`/api/client/track/${token}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || body.error || 'Заявка не найдена или ссылка истекла')
        }
        return res.json()
      })
      .then(setRequest)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  const statusColors: Record<string, string> = {
    NEW: 'bg-blue-600',
    SENT_TO_CLIENT: 'bg-yellow-500 text-gray-900',
    PAID: 'bg-green-600',
    CLIENT_REJECTED: 'bg-red-600',
    CLOSED: 'bg-gray-500',
    MANUAL_REVIEW: 'bg-purple-600',
    READY_FOR_APPROVAL: 'bg-indigo-600',
  }

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-300" role="status">
        Загрузка статуса…
      </div>
    )
  }
  if (error) {
    return (
      <div className="max-w-xl mx-auto p-6">
        <div className="rounded-lg border border-red-500/40 bg-red-950/30 p-5 text-red-200">
          <p className="font-semibold">Нет данных трекинга</p>
          <p className="mt-1 text-sm text-red-200/80">{error}</p>
        </div>
      </div>
    )
  }
  if (!request) {
    return <div className="p-6 text-gray-300">Заявка не найдена</div>
  }

  const parts = request.parts || []
  const vehicleLabel = [request.vehicle_make, request.vehicle_model, request.vehicle_year]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-gray-800 rounded-lg p-6 mb-4 border border-gray-700">
        <h2 className="text-2xl font-bold mb-2">Заявка {request.request_id}</h2>
        <div className="flex items-center gap-2 mb-4">
          <span
            className={`px-3 py-1 rounded-full text-sm font-semibold ${
              statusColors[request.status] || 'bg-gray-500'
            }`}
          >
            {request.status}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-gray-400">Клиент</div>
            <div>{request.customer_name || '—'}</div>
          </div>
          <div>
            <div className="text-gray-400">Автомобиль</div>
            <div>{vehicleLabel || '—'}</div>
          </div>
          {request.erp_quotation_ref && (
            <div>
              <div className="text-gray-400">КП</div>
              <div>{request.erp_quotation_ref}</div>
            </div>
          )}
          {request.erp_invoice_ref && (
            <div>
              <div className="text-gray-400">Счёт</div>
              <div>{request.erp_invoice_ref}</div>
            </div>
          )}
        </div>
      </div>

      {parts.length === 0 ? (
        <div className="bg-gray-800/80 rounded-lg p-6 border border-dashed border-gray-600 text-center">
          <p className="font-semibold text-gray-200">Позиции не опубликованы</p>
          <p className="mt-1 text-sm text-gray-400">Живые строки появятся после подбора и отправки КП.</p>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-bold mb-4">Позиции</h3>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400 text-sm">
                <th className="pb-2 font-medium">Наименование</th>
                <th className="pb-2 font-medium">Кол-во</th>
                <th className="pb-2 font-medium">Цена</th>
              </tr>
            </thead>
            <tbody>
              {parts.map((p, i) => (
                <tr key={i} className="border-b border-gray-800">
                  <td className="py-2">{p.name}</td>
                  <td>{p.quantity || 1}</td>
                  <td>{formatRub(p.sale_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-[11px] text-gray-500">
            Клиентский вид: без закупа, маржи и supplier_id.
          </p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-4">
        {request.status === 'SENT_TO_CLIENT' && (
          <>
            <button
              type="button"
              onClick={() => navigate(`/offer/${token}/accept`)}
              className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded font-semibold"
            >
              Принять предложение
            </button>
            <button
              type="button"
              onClick={() => navigate(`/offer/${token}/reject`)}
              className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded font-semibold"
            >
              Отклонить
            </button>
            <button
              type="button"
              onClick={() => navigate(`/offer/${token}`)}
              className="bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded"
            >
              Открыть КП
            </button>
          </>
        )}
      </div>
    </div>
  )
}
