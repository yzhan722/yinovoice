import { shellMockEnabled } from '@/mocks/shell';
import {
  listCallbackTasks,
  updateCallbackStatus,
  listAppointments,
  listKnowledgeFiles,
  addKnowledgeFile,
  listFollowUps,
  listActivities,
  getHomeSummary,
  getCallStats,
  updateFollowUpStatus,
} from '@/mocks/opsStore';

export class TenantCallbackService {
  list(param = {}) {
    if (!shellMockEnabled()) return Promise.reject(new Error('回拨 API 未对接'));
    return listCallbackTasks(param);
  }
  markDone(id) {
    if (!shellMockEnabled()) return Promise.reject(new Error('回拨 API 未对接'));
    return updateCallbackStatus(id, 'done');
  }
  reopen(id) {
    if (!shellMockEnabled()) return Promise.reject(new Error('回拨 API 未对接'));
    return updateCallbackStatus(id, 'open');
  }
}

export class TenantAppointmentService {
  list() {
    if (!shellMockEnabled()) return Promise.reject(new Error('预约 API 未对接'));
    return listAppointments();
  }
}

export class TenantHomeService {
  summary() {
    if (!shellMockEnabled()) return Promise.reject(new Error('首页汇总 API 未对接'));
    return getHomeSummary();
  }
  followUps(param = {}) {
    if (!shellMockEnabled()) return Promise.reject(new Error('跟进事项 API 未对接'));
    return listFollowUps(param);
  }
  updateFollowUp(id, status) {
    if (!shellMockEnabled()) return Promise.reject(new Error('跟进事项 API 未对接'));
    return updateFollowUpStatus(id, status);
  }
  activities() {
    if (!shellMockEnabled()) return Promise.reject(new Error('动态 API 未对接'));
    return listActivities();
  }
  callStats() {
    if (!shellMockEnabled()) return Promise.reject(new Error('通话统计 API 未对接'));
    return getCallStats();
  }
  appointmentsToday() {
    if (!shellMockEnabled()) return Promise.reject(new Error('Appointment API is not connected'));
    return listAppointments();
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
