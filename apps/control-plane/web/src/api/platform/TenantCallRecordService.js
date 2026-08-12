import {
  DEMO_CUSTOMER_SERVICE_ID,
  RealtimeVoiceService,
} from './RealtimeVoiceService';

/** Tenant facade for tenant-scoped Platform API Demo call records. */
export class TenantCallRecordService {
  /** @param {import('./RealtimeVoiceService').CallRecordFacade & Partial<RealtimeVoiceService>} voiceService */
  constructor(voiceService = new RealtimeVoiceService()) {
    this.voiceService = voiceService;
  }

  async getInstanceOptions() {
    try {
      const service = await this.voiceService.getCustomerService(
        DEMO_CUSTOMER_SERVICE_ID,
      );
      return [{ label: service.display_name, value: service.id }];
    } catch {
      return [];
    }
  }

  getList(param = {}) {
    const pageSize = Number(param.pageSize || 10);
    const page = Number(param.page || param.current || 1);
    return this.voiceService.listNormalizedCallRecords({
      limit: pageSize,
      offset: Math.max(0, page - 1) * pageSize,
    });
  }

  getDetail(recordId) {
    return this.voiceService.getNormalizedCallRecord(String(recordId));
  }

  getStats() {
    return Promise.resolve(null);
  }

  sync() {
    return Promise.reject(new Error('Demo 网页语音记录不支持厂商同步'));
  }

  getAssistantOptions() {
    return this.getInstanceOptions();
  }
}
