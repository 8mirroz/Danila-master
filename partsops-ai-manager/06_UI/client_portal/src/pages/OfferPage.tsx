import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

interface LineItem {
  name?: string
  part_name?: string
  sale_price?: number
  quantity?: number
  match_score?: number
}

interface OfferView {
  request_id: string
  status: string
  parts?: LineItem[]
  erp_invoice_ref?: string
  erp_quotation_ref?: string
}

function formatRub(value: number | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toLocaleString('ru-RU')} ₽`
}

function lineName(p: LineItem): string {
  return p.part_name || p.name || 'Позиция'
}

export function OfferPage({ action }: { action?: 'accept' | 'reject' }) {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [offer, setOffer] = useState<OfferView | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    if (!token || token === 'default') {
      setError('Укажите ссылку из письма или мессенджера (токен трекинга).')
      setLoading(false)
      return
    }
    fetch(`/api/client/track/${token}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || body.error || 'Предложение не найдено или ссылка истекла')
        }
        return res.json()
      })
      .then(setOffer)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  const handleAccept = async () => {
    if (!token || busy) return
    setBusy(true)
    setActionError(null)
    try {
      const res = await fetch(`/api/client/track/${token}/accept`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || body.error || 'Не удалось принять предложение')
      }
      navigate(`/track/${token}`)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  const handleReject = async () => {
    if (!token || busy) return
    setBusy(true)
    setActionError(null)
    try {
      const res = await fetch(`/api/client/track/${token}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: rejectReason }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || body.error || 'Не удалось отклонить предложение')
      }
      navigate(`/track/${token}`)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-300" role="status">
        Загрузка предложения…
      </div>
    )
  }
  if (error) {
    return (
      <div className="max-w-xl mx-auto p-6">
        <div className="rounded-lg border border-red-500/40 bg-red-950/30 p-5 text-red-200">
          <p className="font-semibold">Нет данных предложения</p>
          <p className="mt-1 text-sm text-red-200/80">{error}</p>
          <p className="mt-3 text-xs text-gray-400">
            Демо-пакеты и вымышленные сроки не показываются. Нужна действующая ссылка от оператора.
          </p>
        </div>
      </div>
    )
  }
  if (!offer) {
    return <div className="p-6 text-gray-300">Предложение не найдено</div>
  }

  if (action === 'accept') {
    return (
      <div className="max-w-xl mx-auto">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold mb-4">Подтвердить принятие</h2>
          <p className="mb-6 text-gray-300">
            Принять коммерческое предложение по заявке <strong>{offer.request_id}</strong>?
          </p>
          {actionError && <p className="mb-4 text-sm text-red-400">{actionError}</p>}
          <div className="flex gap-4">
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleAccept()}
              className="bg-green-600 hover:bg-green-700 disabled:opacity-50 px-4 py-2 rounded font-semibold"
            >
              {busy ? 'Отправка…' : 'Да, принять'}
            </button>
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded"
            >
              Отмена
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (action === 'reject') {
    return (
      <div className="max-w-xl mx-auto">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold mb-4">Отклонить предложение</h2>
          <textarea
            className="w-full bg-gray-700 text-white p-3 rounded mb-4 border border-gray-600"
            rows={3}
            placeholder="Причина отклонения (необязательно)"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          {actionError && <p className="mb-4 text-sm text-red-400">{actionError}</p>}
          <div className="flex gap-4">
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleReject()}
              className="bg-red-600 hover:bg-red-700 disabled:opacity-50 px-4 py-2 rounded font-semibold"
            >
              {busy ? 'Отправка…' : 'Подтвердить отклонение'}
            </button>
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded"
            >
              Отмена
            </button>
          </div>
        </div>
      </div>
    )
  }

  const parts = offer.parts || []
  const canAct = offer.status === 'SENT_TO_CLIENT'

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-gray-800 rounded-lg p-6 mb-4 border border-gray-700">
        <h2 className="text-2xl font-bold mb-2">Ваше предложение</h2>
        <p className="text-gray-400">Заявка: {offer.request_id}</p>
        <p className="text-gray-400">Статус: {offer.status}</p>
        {offer.erp_invoice_ref && (
          <p className="text-gray-400">Счёт: {offer.erp_invoice_ref}</p>
        )}
        {offer.erp_quotation_ref && (
          <p className="text-gray-400">КП: {offer.erp_quotation_ref}</p>
        )}
      </div>

      {parts.length === 0 ? (
        <div
          className="bg-gray-800/80 rounded-lg p-6 mb-6 border border-dashed border-gray-600 text-center"
          role="status"
        >
          <p className="font-semibold text-gray-200">Позиции ещё не заполнены</p>
          <p className="mt-1 text-sm text-gray-400">
            Оператор не опубликовал строки заказа. Вымышленные пакеты «Оригинал / Tier-1 / Эконом» не
            показываются.
          </p>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg p-6 mb-6 border border-gray-700">
          <h3 className="text-lg font-bold mb-4">Позиции</h3>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400 text-sm">
                <th className="pb-2 font-medium">Деталь</th>
                <th className="pb-2 font-medium">Кол-во</th>
                <th className="pb-2 font-medium">Цена</th>
              </tr>
            </thead>
            <tbody>
              {parts.map((p, i) => (
                <tr key={i} className="border-b border-gray-800">
                  <td className="py-2">{lineName(p)}</td>
                  <td className="py-2">{p.quantity ?? 1}</td>
                  <td className="py-2 text-emerald-400 font-semibold">{formatRub(p.sale_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-[11px] text-gray-500">
            Цены клиентские; закупка и маржа скрыты. Совпадение match_score не показывается клиенту.
          </p>
        </div>
      )}

      {canAct ? (
        <div className="mt-2 flex flex-wrap gap-4">
          <button
            type="button"
            onClick={() => navigate(`/offer/${token}/accept`)}
            className="bg-green-600 hover:bg-green-700 px-6 py-3 rounded font-bold"
          >
            Принять
          </button>
          <button
            type="button"
            onClick={() => navigate(`/offer/${token}/reject`)}
            className="bg-red-600 hover:bg-red-700 px-6 py-3 rounded font-bold"
          >
            Отклонить
          </button>
        </div>
      ) : (
        <p className="text-sm text-gray-400">
          Действия accept/reject доступны только в статусе SENT_TO_CLIENT (текущий: {offer.status}).
        </p>
      )}
    </div>
  )
}
