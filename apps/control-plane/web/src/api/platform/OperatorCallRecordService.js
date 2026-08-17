import { RealtimeVoiceService } from './RealtimeVoiceService';

/**
 * Operator Demo facade.
 * It intentionally uses the configured demo tenant header; this is not global RBAC.
 */
export class OperatorCallRecordService {
  /** @param {import('./RealtimeVoiceService').CallRecordFacade} voiceService */
  constructor(voiceService = new RealtimeVoiceService()) {
    this.voiceService = voiceService;
  }

  getList(param = {}) {
    const pageSize = Number(param.pageSize || 10);
    const page = Number(param.current || param.page || 1);
    return this.voiceService.listNormalizedCallRecords({
      limit: pageSize,
      offset: Math.max(0, page - 1) * pageSize,
      includeDeleted: Boolean(param.includeDeleted),
    });
  }

  getDetail(recordId) {
    return this.voiceService.getNormalizedCallRecord(String(recordId));
  }

  update(recordId, update) {
    return this.voiceService.updateCallRecord(String(recordId), update);
  }

  remove(recordId) {
    return this.voiceService.deleteCallRecord(String(recordId));
  }

  restore(recordId) {
    return this.voiceService.restoreCallRecord(String(recordId));
  }

  sync() {
    return Promise.reject(new Error('Demo 网页语音记录不支持厂商同步'));
  }
}
