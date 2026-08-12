import {
  shellMockEnabled,
} from '@/mocks/shell';
import {
  listTemplates,
  getTemplate,
  setTemplateStatus,
  listInstances,
  createInstanceFromTemplate,
} from '@/mocks/templateStore';

/** Platform Operator — Agent Template catalog */
export class OperatorTemplateService {
  list(param = {}) {
    if (!shellMockEnabled()) {
      return Promise.reject(new Error('Platform Core 模板 API 尚未对接；请启用 VITE_SHELL_MOCK'));
    }
    return listTemplates({ publishedOnly: !!param.publishedOnly });
  }

  get(id) {
    if (!shellMockEnabled()) {
      return Promise.reject(new Error('Platform Core 模板 API 尚未对接'));
    }
    return getTemplate(id);
  }

  publish(id) {
    return setTemplateStatus(id, 'published');
  }

  disable(id) {
    return setTemplateStatus(id, 'disabled');
  }

  setDraft(id) {
    return setTemplateStatus(id, 'draft');
  }
}

/** Tenant — create Voice Agent Instance from published template */
export class TenantInstanceFactoryService {
  listPublishedTemplates() {
    if (!shellMockEnabled()) {
      return Promise.reject(new Error('Platform Core 模板 API 尚未对接'));
    }
    return listTemplates({ publishedOnly: true });
  }

  getTemplate(id) {
    return getTemplate(id);
  }

  listMyInstances() {
    if (!shellMockEnabled()) {
      return Promise.reject(new Error('Platform Core 实例 API 尚未对接'));
    }
    return listInstances();
  }

  createFromTemplate(payload) {
    if (!shellMockEnabled()) {
      return Promise.reject(new Error('Platform Core 实例 API 尚未对接'));
    }
    return createInstanceFromTemplate(payload);
  }
}
