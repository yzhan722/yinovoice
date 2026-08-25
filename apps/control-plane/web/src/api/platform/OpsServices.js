import { shellMockEnabled } from '@/mocks/shell';
import {
  listKnowledgeFiles,
  addKnowledgeFile,
  listFollowUps,
  listActivities,
  getHomeSummary,
  getCallStats,
  updateFollowUpStatus,
  listAppointments as listMockAppointments,
} from '@/mocks/opsStore';
import { DEMO_TENANT_ID } from './RealtimeVoiceService';

function platformBase() {
  return String(import.meta.env.VITE_PLATFORM_API_BASE || 'http://localhost:8000').replace(
    /\/+$/,
    '',
  );
}

async function platformRequest(path, init = {}) {
  const response = await fetch(platformBase() + path, {
    ...init,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'X-Tenant-ID': DEMO_TENANT_ID,
      ...(init.headers || {}),
    },
  });
  if (response.status === 204) return null;
  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = typeof body?.detail === 'string' ? body.detail : '';
    } catch (_) {
      detail = '';
    }
    if (detail === '日期不可使用' || detail.includes('slot_end')) {
      throw new Error('日期不可使用');
    }
    throw new Error('平台服务暂时不可用，请稍后重试');
  }
  return response.json();
}

function mapAppointment(row) {
  return {
    id: row.id,
    status: row.status,
    patientName: row.patient_name,
    phone: row.phone,
    service: row.service,
    slotStart: row.slot_start,
    slotEnd: row.slot_end,
    instanceId: row.voice_agent_instance_id,
    callRecordId: row.call_record_id || null,
    source: row.source,
    notes: row.notes || '',
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    raw: row,
  };
}

function mapCallback(row) {
  return {
    id: row.id,
    status: row.status,
    reason: row.reason,
    callerPhone: row.caller_phone,
    summary: row.summary || '',
    instanceId: row.voice_agent_instance_id,
    source: row.source,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    raw: row,
  };
}

export class TenantCallbackService {
  async list(param = {}) {
    const qs = new URLSearchParams({
      limit: String(param.limit ?? 50),
      offset: String(param.offset ?? 0),
    });
    if (param.status) qs.set('status', param.status);
    if (param.includeCancelled) qs.set('include_cancelled', 'true');
    const page = await platformRequest(`/api/v1/callback-tasks?${qs.toString()}`);
    return { list: (page.items || []).map(mapCallback), total: page.total ?? 0 };
  }

  async create(input) {
    const row = await platformRequest('/api/v1/callback-tasks', {
      method: 'POST',
      body: JSON.stringify({
        caller_phone: input.callerPhone,
        reason: input.reason,
        summary: input.summary || '',
        voice_agent_instance_id: input.instanceId || null,
      }),
    });
    return mapCallback(row);
  }

  async markDone(id) {
    const row = await platformRequest(
      `/api/v1/callback-tasks/${encodeURIComponent(id)}/complete`,
      { method: 'POST' },
    );
    return mapCallback(row);
  }

  async reopen(id) {
    const row = await platformRequest(
      `/api/v1/callback-tasks/${encodeURIComponent(id)}/reopen`,
      { method: 'POST' },
    );
    return mapCallback(row);
  }
}

export class TenantAppointmentService {
  async list(param = {}) {
    const qs = new URLSearchParams({
      limit: String(param.limit ?? 50),
      offset: String(param.offset ?? 0),
    });
    if (param.status) qs.set('status', param.status);
    if (param.includeCancelled) qs.set('include_cancelled', 'true');
    const page = await platformRequest(`/api/v1/appointments?${qs.toString()}`);
    return { list: (page.items || []).map(mapAppointment), total: page.total ?? 0 };
  }

  async create(input) {
    const row = await platformRequest('/api/v1/appointments', {
      method: 'POST',
      body: JSON.stringify({
        patient_name: input.patientName,
        phone: input.phone,
        service: input.service,
        slot_start: input.slotStart,
        slot_end: input.slotEnd,
        voice_agent_instance_id: input.instanceId || null,
        notes: input.notes || '',
        status: input.status || 'pending',
      }),
    });
    return mapAppointment(row);
  }

  async update(id, patch) {
    const body = {};
    if (patch.patientName != null) body.patient_name = patch.patientName;
    if (patch.phone != null) body.phone = patch.phone;
    if (patch.service != null) body.service = patch.service;
    if (patch.slotStart != null) body.slot_start = patch.slotStart;
    if (patch.slotEnd != null) body.slot_end = patch.slotEnd;
    if (patch.status != null) body.status = patch.status;
    if (patch.notes != null) body.notes = patch.notes;
    const row = await platformRequest(
      `/api/v1/appointments/${encodeURIComponent(id)}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    );
    return mapAppointment(row);
  }

  async cancel(id) {
    await platformRequest(`/api/v1/appointments/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  }
}

export class TenantHomeService {
  async summary() {
    try {
      return await platformRequest('/api/v1/dashboard/summary');
    } catch (error) {
      if (shellMockEnabled()) return getHomeSummary();
      throw error;
    }
  }
  async followUps(param = {}) {
    try {
      const page = await new TenantCallbackService().list({
        status: 'open',
        limit: param.limit ?? 20,
      });
      return {
        list: (page.list || []).map((item) => ({
          id: item.id,
          title: item.reason,
          status: item.status === 'open' ? 'todo' : item.status === 'done' ? 'done' : 'doing',
        })),
      };
    } catch (error) {
      if (shellMockEnabled()) return listFollowUps(param);
      return { list: [] };
    }
  }
  updateFollowUp(id, status) {
    if (!shellMockEnabled()) return Promise.reject(new Error('跟进事项 API 未对接'));
    return updateFollowUpStatus(id, status);
  }
  activities() {
    if (!shellMockEnabled()) return Promise.reject(new Error('动态 API 未对接'));
    return listActivities();
  }
  async callStats() {
    try {
      const summary = await this.summary();
      return summary.callStats || getCallStats();
    } catch (error) {
      if (shellMockEnabled()) return getCallStats();
      throw error;
    }
  }
  appointmentsToday() {
    return new TenantAppointmentService().list().catch(() => {
      if (!shellMockEnabled()) {
        return Promise.reject(new Error('Appointment API is not connected'));
      }
      return listMockAppointments();
    });
  }
}

export class TenantPhoneNumberService {
  async list() {
    const page = await platformRequest('/api/v1/phone-numbers');
    return page.items || page || [];
  }
  async create(input) {
    return platformRequest('/api/v1/phone-numbers', {
      method: 'POST',
      body: JSON.stringify({
        e164_number: input.e164Number,
        voice_agent_instance_id: input.instanceId,
      }),
    });
  }
  async remove(id) {
    await platformRequest(`/api/v1/phone-numbers/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  }
}

export class TenantSchedulingService {
  listOfferings(instanceId) {
    const qs = new URLSearchParams({ voice_agent_instance_id: instanceId });
    return platformRequest(`/api/v1/service-offerings?${qs.toString()}`);
  }
  createOffering(input) {
    return platformRequest('/api/v1/service-offerings', {
      method: 'POST',
      body: JSON.stringify({
        voice_agent_instance_id: input.instanceId,
        name: input.name,
        duration_minutes: Number(input.durationMinutes || 30),
        buffer_minutes: Number(input.bufferMinutes || 0),
      }),
    });
  }
  putProfile(instanceId, input) {
    return platformRequest(`/api/v1/scheduling-profiles/${encodeURIComponent(instanceId)}`, {
      method: 'PUT',
      body: JSON.stringify({
        timezone: input.timezone,
        slot_interval_minutes: Number(input.slotIntervalMinutes || 15),
        minimum_notice_minutes: Number(input.minimumNoticeMinutes || 60),
        booking_horizon_days: Number(input.bookingHorizonDays || 60),
      }),
    });
  }
  getProfile(instanceId) {
    return platformRequest(`/api/v1/scheduling-profiles/${encodeURIComponent(instanceId)}`);
  }
  listHours(instanceId) {
    const qs = new URLSearchParams({ voice_agent_instance_id: instanceId });
    return platformRequest(`/api/v1/business-hours?${qs.toString()}`);
  }
  putHours(instanceId, hours) {
    const qs = new URLSearchParams({ voice_agent_instance_id: instanceId });
    return platformRequest(`/api/v1/business-hours?${qs.toString()}`, {
      method: 'PUT',
      body: JSON.stringify(hours),
    });
  }
  listAvailability(params) {
    const qs = new URLSearchParams({
      voice_agent_instance_id: params.instanceId,
      service_offering_id: params.offeringId,
      date_from: params.dateFrom,
      date_to: params.dateTo,
    });
    return platformRequest(`/api/v1/availability?${qs.toString()}`);
  }
}

export class TenantNotificationService {
  get() {
    return platformRequest('/api/v1/notification-settings');
  }
  put(input) {
    return platformRequest('/api/v1/notification-settings', {
      method: 'PUT',
      body: JSON.stringify({
        email: input.email || '',
        enabled: Boolean(input.enabled),
      }),
    });
  }
}

export class TenantToolInvocationService {
  listByCallRecord(callRecordId) {
    const qs = new URLSearchParams({ call_record_id: callRecordId });
    return platformRequest(`/api/v1/tool-invocations?${qs.toString()}`);
  }
}

export class TenantKnowledgeMock {
  listMine(param = {}) {
    return listKnowledgeFiles({ scope: 'mine' }).then((res) => ({
      records: res.list,
      total: res.total,
      ...param,
    }));
  }
  listAssociated() {
    return listKnowledgeFiles({ scope: 'associated' }).then((res) => res.list);
  }
  upload(file) {
    return addKnowledgeFile({
      filName: file?.name || 'upload.bin',
      filSizeBytes: file?.size || 0,
      filMimeType: file?.type || 'application/octet-stream',
    });
  }
}
