/**
 * Call system integration contract (Path A).
 * Flip VITE_CALL_SYSTEM_READY=true and optionally set VITE_CALL_API_BASE
 * when the shared call project is available — only change this file + env if paths differ.
 *
 * @typedef {Object} CallListItem
 * @property {string|number} aacId
 * @property {string} callId
 * @property {string} [assistantName]
 * @property {number|string} [attId]
 * @property {'inbound'|'outbound'|string} [direction]
 * @property {string} [status]
 * @property {string} [startedAt]
 * @property {number} [durationSec]
 * @property {string} [customerPhone]
 * @property {number} [success] 1|0
 *
 * @typedef {Object} CallDetail
 * @property {string|number} aacId
 * @property {string} callId
 * @property {number} [aacSuccess]
 * @property {number} [aacDurationSec]
 * @property {number} [aacTotalCost]
 * @property {string} [aacRecordingUrl]
 * @property {string} [aacSummary]
 * @property {string} [aacCustomerPhone]
 * @property {string} [aacStartedAt]
 * @property {string} [attName]
 * @property {Array<{role:string,content?:string,message?:string}>} [messages]
 */

/** Relative paths appended to VITE_CALL_API_BASE (or legacy BASE_API when empty). */
export const CALL_API_PATHS = {
  LIST: 'api/tenant/calls/list',
  DETAIL: 'api/tenant/calls/detail',
  STATS: 'api/tenant/calls/stats',
  INSTANCE_OPTIONS: 'api/tenant/instances/options',
};

/**
 * Legacy AVM paths — used when VITE_CALL_API_BASE is empty but system is ready.
 * Prefer migrating call service to CALL_API_PATHS.
 */
export const CALL_API_PATHS_LEGACY = {
  LIST: null, // resolved via UserEnum at runtime
  DETAIL: null,
};

export function callApiBase() {
  const raw = String(import.meta.env.VITE_CALL_API_BASE || '').trim();
  if (!raw) return '';
  return raw.endsWith('/') ? raw : `${raw}/`;
}

/** Normalize heterogeneous list payloads into table rows. */
export function normalizeCallListResponse(res) {
  const records = res?.records || res?.list || res?.items || res?.data?.records || res?.data?.list || [];
  const total = res?.total ?? res?.data?.total ?? records.length;
  const list = (Array.isArray(records) ? records : []).map(normalizeCallListItem);
  return { records: list, list, total };
}

export function normalizeCallListItem(row = {}) {
  return {
    aacId: row.aacId ?? row.id ?? row.call_record_id,
    callId: String(row.callId ?? row.call_id ?? row.vendorCallId ?? row.aacId ?? ''),
    assistantName: row.assistantName ?? row.attName ?? row.instanceName ?? row.att_name ?? '',
    attId: row.attId ?? row.att_id ?? row.instanceId,
    direction: row.direction ?? row.callDirection ?? row.aacType ?? '',
    status: row.status ?? row.callStatus ?? (row.aacSuccess === 1 ? 'completed' : row.aacSuccess === 0 ? 'failed' : ''),
    startedAt: row.startedAt ?? row.aacStartedAt ?? row.started_at ?? row.createTime ?? '',
    durationSec: row.durationSec ?? row.aacDurationSec ?? row.duration_sec ?? null,
    customerPhone: row.customerPhone ?? row.aacCustomerPhone ?? row.customer_phone ?? '',
    success: row.success ?? row.aacSuccess,
    raw: row,
  };
}

export function normalizeCallDetail(res) {
  const row = res?.data ?? res ?? {};
  return {
    ...row,
    aacId: row.aacId ?? row.id,
    callId: row.callId ?? row.call_id ?? '',
    aacSuccess: row.aacSuccess ?? row.success,
    aacDurationSec: row.aacDurationSec ?? row.durationSec,
    aacTotalCost: row.aacTotalCost ?? row.totalCost,
    aacRecordingUrl: row.aacRecordingUrl ?? row.recordingUrl,
    aacSummary: row.aacSummary ?? row.summary,
    aacCustomerPhone: row.aacCustomerPhone ?? row.customerPhone,
    aacStartedAt: row.aacStartedAt ?? row.startedAt,
    attName: row.attName ?? row.assistantName ?? row.instanceName,
    messages: row.messages ?? row.transcript ?? row.records ?? [],
  };
}
