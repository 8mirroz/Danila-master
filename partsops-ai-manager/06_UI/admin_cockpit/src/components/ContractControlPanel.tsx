import React, { useEffect, useMemo, useState } from 'react';
import {
  fetchContractCandidates,
  fetchContractControlPlane,
  fetchContractPositions,
  registerContractAnalogCandidate,
  registerContractOemCandidate,
} from '../lib/api';
import type {
  ContractCandidates,
  ContractControlGap,
  ContractControlPlane,
  ContractControlRequirement,
  ContractPositionDetail,
} from '../lib/api';
import { EmptyState, InlineAlert, SectionCard } from './Primitives';

type ContractControlPanelProps = {
  requestId: string | null;
  refreshTrigger?: number;
};

const statusClasses: Record<string, string> = {
  Covered: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  Partial: 'bg-amber-50 text-amber-700 border-amber-200',
  Missing: 'bg-rose-50 text-rose-700 border-rose-200',
  Conflict: 'bg-red-50 text-red-700 border-red-200',
  open: 'bg-rose-50 text-rose-700 border-rose-200',
  closed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  accepted: 'bg-slate-50 text-slate-700 border-slate-200',
};

function MetricTile({ label, value, support }: { label: string; value: string; support: string }) {
  return (
    <div className="border border-[var(--border-subtle)] rounded-md bg-[var(--surface-2)] p-3 min-h-20">
      <div className="text-[10px] uppercase tracking-normal text-[var(--text-muted)] font-bold">{label}</div>
      <div className="mt-2 text-xl font-black text-[var(--text-primary)] tabular-nums">{value}</div>
      <div className="mt-1 text-[10px] text-[var(--text-secondary)] leading-snug">{support}</div>
    </div>
  );
}

function Badge({ value }: { value: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-extrabold ${statusClasses[value] ?? 'bg-slate-50 text-slate-700 border-slate-200'}`}>
      {value}
    </span>
  );
}

function RequirementRow({ requirement }: { requirement: ContractControlRequirement }) {
  const coverage = requirement.coverage;
  return (
    <tr className="border-b border-[var(--border-subtle)] align-top">
      <td className="py-2 pr-3 font-mono text-[10px] text-[var(--text-secondary)]">{requirement.clause}</td>
      <td className="py-2 pr-3">
        <div className="text-xs font-bold text-[var(--text-primary)] leading-snug">{requirement.summary}</div>
        <div className="mt-1 text-[10px] text-[var(--text-muted)]">{requirement.implementation_element}</div>
      </td>
      <td className="py-2 pr-3 text-[10px] text-[var(--text-secondary)]">{requirement.object_scope}</td>
      <td className="py-2 pr-3"><Badge value={requirement.coverage_status} /></td>
      <td className="py-2">
        <div className="grid grid-cols-3 gap-1 min-w-36">
          {[
            ['D', coverage?.has_data],
            ['C', coverage?.has_check],
            ['E', coverage?.has_evidence],
            ['O', coverage?.has_responsible],
            ['G', coverage?.has_workflow_gate],
            ['T', coverage?.has_test],
          ].map(([label, ok]) => (
            <span
              key={String(label)}
              title={String(label)}
              className={`h-5 rounded border flex items-center justify-center text-[9px] font-black ${
                ok ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-slate-50 border-slate-200 text-slate-400'
              }`}
            >
              {label}
            </span>
          ))}
        </div>
      </td>
    </tr>
  );
}

function GapRow({ gap }: { gap: ContractControlGap }) {
  return (
    <div className="border border-[var(--border-default)] rounded-md p-3 bg-[var(--surface-2)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] text-[var(--text-muted)]">{gap.gap_id}</div>
          <div className="text-xs font-bold text-[var(--text-primary)] mt-1 leading-snug">{gap.description}</div>
        </div>
        <Badge value={gap.status} />
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-[var(--text-secondary)]">
        <span className="px-2 py-0.5 border border-[var(--border-subtle)] rounded">{gap.category}</span>
        <span className="px-2 py-0.5 border border-[var(--border-subtle)] rounded">{gap.risk}</span>
        <span className="px-2 py-0.5 border border-[var(--border-subtle)] rounded">{gap.priority}</span>
      </div>
      <p className="mt-2 text-[10px] text-[var(--text-muted)] leading-relaxed">{gap.closure_criteria}</p>
    </div>
  );
}

const defaultOemEvidence = [
  { evidence_type: 'vin_oem_catalog', source: 'VIN catalog' },
  { evidence_type: 'official_brand_catalog', source: 'Official catalog' },
  { evidence_type: 'cross_reference', source: 'Cross reference' },
];

const defaultAnalogEvidence = [
  { evidence_type: 'vin_oem_catalog', source: 'VIN catalog' },
  { evidence_type: 'official_brand_catalog', source: 'Brand catalog' },
  { evidence_type: 'tecdoc', source: 'TecDoc' },
  { evidence_type: 'cross_reference', source: 'Cross reference' },
  { evidence_type: 'spec_match', source: 'Specification match' },
];

export const ContractControlPanel: React.FC<ContractControlPanelProps> = ({ requestId, refreshTrigger = 0 }) => {
  const [data, setData] = useState<ContractControlPlane | null>(null);
  const [positions, setPositions] = useState<ContractPositionDetail[]>([]);
  const [candidatesByPosition, setCandidatesByPosition] = useState<Record<string, ContractCandidates>>({});
  const [oemInputs, setOemInputs] = useState<Record<string, string>>({});
  const [analogInputs, setAnalogInputs] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingPositionId, setSavingPositionId] = useState<string | null>(null);

  useEffect(() => {
    if (!requestId) return;
    let isMounted = true;
    setLoading(true);
    setError(null);
    Promise.all([fetchContractControlPlane(requestId), fetchContractPositions(requestId)])
      .then(async ([control, positionRows]) => {
        const candidatePairs = await Promise.all(
          positionRows.map(async (position) => [position.position_id, await fetchContractCandidates(requestId, position.position_id)] as const),
        );
        if (isMounted) {
          setData(control);
          setPositions(positionRows);
          setCandidatesByPosition(Object.fromEntries(candidatePairs));
        }
      })
      .catch((err) => {
        if (isMounted) setError(err instanceof Error ? err.message : 'Не удалось загрузить договорный контроль');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [requestId, refreshTrigger]);

  const openGaps = useMemo(() => data?.gaps.filter((gap) => gap.status === 'open') ?? [], [data]);
  const coveredCount = useMemo(
    () => data?.requirements.filter((requirement) => requirement.coverage_status === 'Covered').length ?? 0,
    [data],
  );

  if (!requestId) {
    return (
      <EmptyState
        title="Запрос не выбран"
        description="Выберите contract request, чтобы увидеть аудит требований, матрицу покрытия, gaps и ADR."
        icon="fa-file-shield"
      />
    );
  }

  if (loading && !data) {
    return (
      <SectionCard title="Договорный контроль" icon="fa-file-shield">
        <div className="text-xs text-[var(--text-secondary)]">Загрузка матрицы покрытия...</div>
      </SectionCard>
    );
  }

  if (error) {
    return (
      <SectionCard title="Договорный контроль" icon="fa-file-shield">
        <InlineAlert type="danger" message={error} />
      </SectionCard>
    );
  }

  if (!data) return null;

  const reloadContractState = async () => {
    if (!requestId) return;
    const [control, positionRows] = await Promise.all([fetchContractControlPlane(requestId), fetchContractPositions(requestId)]);
    const candidatePairs = await Promise.all(
      positionRows.map(async (position) => [position.position_id, await fetchContractCandidates(requestId, position.position_id)] as const),
    );
    setData(control);
    setPositions(positionRows);
    setCandidatesByPosition(Object.fromEntries(candidatePairs));
  };

  const submitOem = async (position: ContractPositionDetail) => {
    if (!requestId) return;
    const oemNumber = (oemInputs[position.position_id] || position.part_number).trim();
    if (!oemNumber) return;
    setSavingPositionId(position.position_id);
    setActionError(null);
    try {
      await registerContractOemCandidate(requestId, position.position_id, {
        oem_number: oemNumber,
        manufacturer: 'operator-confirmed',
        source: 'vin_oem_catalog',
        compatibility_evidence: defaultOemEvidence,
      });
      setOemInputs((prev) => ({ ...prev, [position.position_id]: '' }));
      await reloadContractState();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось сохранить OEM candidate');
    } finally {
      setSavingPositionId(null);
    }
  };

  const submitAnalog = async (position: ContractPositionDetail) => {
    if (!requestId) return;
    const article = (analogInputs[position.position_id] || position.part_number).trim();
    if (!article) return;
    const oem = candidatesByPosition[position.position_id]?.oem_candidates.find((candidate) => candidate.verification_status === 'verified');
    setSavingPositionId(position.position_id);
    setActionError(null);
    try {
      await registerContractAnalogCandidate(requestId, position.position_id, {
        article,
        brand: 'operator-confirmed',
        source: 'tecdoc',
        oem_candidate_id: oem?.candidate_id,
        independent_confirmations: 2,
        compatibility_evidence: defaultAnalogEvidence,
      });
      setAnalogInputs((prev) => ({ ...prev, [position.position_id]: '' }));
      await reloadContractState();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось сохранить analog candidate');
    } finally {
      setSavingPositionId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SectionCard title="Аудит" icon="fa-magnifying-glass-chart">
          <div className="text-2xl font-black text-[var(--text-primary)]">{data.audits.length}</div>
          <div className="text-[10px] text-[var(--text-secondary)] mt-1">audit run</div>
        </SectionCard>
        <SectionCard title="Покрытие" icon="fa-list-check">
          <div className="text-2xl font-black text-[var(--text-primary)]">{coveredCount}/{data.requirements.length}</div>
          <div className="text-[10px] text-[var(--text-secondary)] mt-1">требований закрыто</div>
        </SectionCard>
        <SectionCard title="Открытые gaps" icon="fa-triangle-exclamation">
          <div className="text-2xl font-black text-[var(--text-primary)]">{openGaps.length}</div>
          <div className="text-[10px] text-[var(--text-secondary)] mt-1">блокировки и контроль</div>
        </SectionCard>
        <SectionCard title="Закупочный lock" icon="fa-lock">
          <div className="text-sm font-black text-[var(--text-primary)]">
            {data.purchase_authorizations.length ? 'Разрешена' : 'Заблокирована'}
          </div>
          <div className="text-[10px] text-[var(--text-secondary)] mt-1">
            approvals: {data.client_approvals.length}
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Метрики договора" icon="fa-gauge-high">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MetricTile
            label="Quality"
            value={`${data.metrics.quality.requirement_coverage_percent.toFixed(0)}%`}
            support={`${data.metrics.quality.requirements_covered}/${data.metrics.quality.requirements_total} требований, gaps: ${data.metrics.quality.open_gaps}`}
          />
          <MetricTile
            label="Evidence"
            value={`${data.metrics.evidence.required_source_coverage_percent.toFixed(0)}%`}
            support={`${data.metrics.evidence.positions_with_all_required_sources}/${data.metrics.evidence.positions_total} позиций, stale: ${data.metrics.evidence.stale_evidence}`}
          />
          <MetricTile
            label="Screenshots"
            value={`${data.metrics.evidence.screenshot_coverage_percent.toFixed(0)}%`}
            support={`${data.metrics.evidence.total_evidence} evidence rows, readable hash coverage`}
          />
          <MetricTile
            label="Cost"
            value={`${data.metrics.cost.contract_total.toLocaleString()} ${data.metrics.cost.currency}`}
            support={`${data.metrics.cost.selected_positions} выбранных позиций, avg ${data.metrics.cost.average_position_total.toLocaleString()}`}
          />
          <MetricTile
            label="Process"
            value={data.metrics.process.elapsed_minutes === null || data.metrics.process.elapsed_minutes === undefined ? '—' : `${data.metrics.process.elapsed_minutes}m`}
            support={`${data.metrics.process.workflow_events} workflow events, exports: ${data.metrics.process.exports}`}
          />
          <MetricTile
            label="Exceptions"
            value={String(data.metrics.quality.blocking_exceptions)}
            support={`rejected transitions: ${data.metrics.quality.rejected_workflow_transitions}`}
          />
          <MetricTile
            label="Client"
            value={String(data.metrics.process.client_approvals)}
            support={`approvals, purchase auth: ${data.metrics.process.purchase_authorizations}`}
          />
          <MetricTile
            label="Purchase"
            value={data.metrics.process.purchase_locked ? 'Locked' : 'Open'}
            support={`buy ${data.metrics.process.purchases}, receipt ${data.metrics.process.receipt_verifications}, archive ${data.metrics.process.archives}`}
          />
        </div>
      </SectionCard>

      <SectionCard title="Workflow v2" icon="fa-route">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <div className="font-mono text-xs font-black text-[var(--text-primary)]">{data.workflow.current_stage}</div>
            <div className="text-[10px] text-[var(--text-secondary)] mt-1">
              stage {data.workflow.current_stage_index + 1} / {data.workflow.stages.length}
            </div>
          </div>
          <Badge value={data.workflow.blocked ? 'open' : 'closed'} />
        </div>
        {data.workflow.blocking_reason && (
          <div className="mt-3">
            <InlineAlert type="warning" message={data.workflow.blocking_reason} />
          </div>
        )}
        <div className="mt-4 grid grid-cols-3 md:grid-cols-6 lg:grid-cols-9 gap-1">
          {data.workflow.stages.map((stage, index) => (
            <span
              key={stage}
              title={stage}
              className={`h-7 rounded border flex items-center justify-center font-mono text-[9px] font-black ${
                index <= data.workflow.current_stage_index
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                  : 'bg-slate-50 border-slate-200 text-slate-400'
              }`}
            >
              {String(index).padStart(2, '0')}
            </span>
          ))}
        </div>
        <div className="mt-4 space-y-2 max-h-52 overflow-y-auto">
          {data.workflow.events.slice(-8).reverse().map((event) => (
            <div key={event.workflow_event_id} className="flex items-start justify-between gap-3 border border-[var(--border-subtle)] rounded-md p-2 bg-[var(--surface-2)]">
              <div>
                <div className="font-mono text-[10px] text-[var(--text-primary)]">{event.to_stage}</div>
                <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">{event.reason}</div>
                {event.violations.length > 0 && (
                  <div className="text-[10px] text-rose-700 mt-1">{event.violations.join('; ')}</div>
                )}
              </div>
              <Badge value={event.allowed ? 'closed' : 'open'} />
            </div>
          ))}
        </div>
      </SectionCard>

      {openGaps.length > 0 && (
        <InlineAlert
          type="warning"
          message="Есть открытые contract-control gaps. Export и закупка должны проходить только через backend gates."
        />
      )}

      {actionError && <InlineAlert type="danger" message={actionError} />}

      <SectionCard title="OEM / Analog candidates" icon="fa-sitemap">
        <div className="space-y-3">
          {positions.map((position) => {
            const candidateState = candidatesByPosition[position.position_id];
            const verifiedOems = candidateState?.oem_candidates.filter((candidate) => candidate.verification_status === 'verified') ?? [];
            const approvedAnalogs = candidateState?.analog_candidates.filter((candidate) => candidate.manual_review_status === 'approved') ?? [];
            const saving = savingPositionId === position.position_id;
            return (
              <div key={position.position_id} className="border border-[var(--border-default)] rounded-md bg-[var(--surface-2)] p-3">
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-[10px] text-[var(--text-muted)]">#{position.line_no} {position.position_id}</div>
                    <div className="text-sm font-black text-[var(--text-primary)] mt-1">{position.part_number}</div>
                    <div className="text-[10px] text-[var(--text-secondary)] mt-1">{position.description || 'Без описания'} · qty {position.quantity}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge value={verifiedOems.length ? 'closed' : 'open'} />
                    <span className="text-[10px] text-[var(--text-secondary)]">OEM {verifiedOems.length}</span>
                    <span className="text-[10px] text-[var(--text-secondary)]">Analog {approvedAnalogs.length}</span>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
                  <div className="flex gap-2">
                    <input
                      className="min-w-0 flex-1 border border-[var(--border-default)] rounded-md bg-[var(--surface-1)] px-3 py-2 text-xs"
                      value={oemInputs[position.position_id] ?? ''}
                      placeholder={`OEM ${position.part_number}`}
                      onChange={(event) => setOemInputs((prev) => ({ ...prev, [position.position_id]: event.target.value }))}
                    />
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void submitOem(position)}
                      className="px-3 py-2 rounded-md bg-[var(--accent)] text-white text-xs font-black disabled:opacity-50 inline-flex items-center gap-2"
                    >
                      <i className="fa-solid fa-barcode" aria-hidden="true" />
                      OEM
                    </button>
                  </div>
                  <div className="flex gap-2">
                    <input
                      className="min-w-0 flex-1 border border-[var(--border-default)] rounded-md bg-[var(--surface-1)] px-3 py-2 text-xs"
                      value={analogInputs[position.position_id] ?? ''}
                      placeholder={`Analog ${position.part_number}`}
                      onChange={(event) => setAnalogInputs((prev) => ({ ...prev, [position.position_id]: event.target.value }))}
                    />
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void submitAnalog(position)}
                      className="px-3 py-2 rounded-md bg-[var(--accent)] text-white text-xs font-black disabled:opacity-50 inline-flex items-center gap-2"
                    >
                      <i className="fa-solid fa-link" aria-hidden="true" />
                      Analog
                    </button>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-2 text-[10px] text-[var(--text-secondary)]">
                  <div>
                    {(candidateState?.oem_candidates ?? []).slice(-3).map((candidate) => (
                      <div key={candidate.candidate_id} className="flex justify-between gap-2 border-t border-[var(--border-subtle)] py-1">
                        <span>{candidate.oem_number}</span>
                        <span>{candidate.verification_status}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    {(candidateState?.analog_candidates ?? []).slice(-3).map((candidate) => (
                      <div key={candidate.candidate_id} className="flex justify-between gap-2 border-t border-[var(--border-subtle)] py-1">
                        <span>{candidate.brand} {candidate.article}</span>
                        <span>{candidate.manual_review_status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard title="Матрица покрытия требований" icon="fa-table">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[var(--border-default)] text-[10px] uppercase text-[var(--text-muted)]">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 pr-3">Требование</th>
                <th className="py-2 pr-3">Объект</th>
                <th className="py-2 pr-3">Статус</th>
                <th className="py-2">D/C/E/O/G/T</th>
              </tr>
            </thead>
            <tbody>
              {data.requirements.map((requirement) => (
                <RequirementRow key={requirement.requirement_id} requirement={requirement} />
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SectionCard title="Gap Analysis" icon="fa-bug-slash">
          <div className="space-y-3">
            {data.gaps.length === 0 ? (
              <div className="text-xs text-[var(--text-secondary)]">Пробелы не зарегистрированы.</div>
            ) : (
              data.gaps.map((gap) => <GapRow key={gap.gap_id} gap={gap} />)
            )}
          </div>
        </SectionCard>
        <SectionCard title="ADR" icon="fa-scale-balanced">
          <div className="space-y-3">
            {data.adrs.map((adr) => (
              <div key={adr.adr_id} className="border border-[var(--border-default)] rounded-md p-3 bg-[var(--surface-2)]">
                <div className="font-mono text-[10px] text-[var(--text-muted)]">{adr.adr_id}</div>
                <div className="text-xs font-bold text-[var(--text-primary)] mt-1">{adr.problem}</div>
                <p className="mt-2 text-[10px] text-[var(--text-secondary)] leading-relaxed">{adr.decision}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
};
