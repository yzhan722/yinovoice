import { CUSTOMER_SERVICE_VERSION_CONFLICT } from './RealtimeVoiceService';
import { platformApiBase, platformAuthHeaders } from './platformSession';

export class TenantKnowledgeService {
  async list(instanceId) {
    const page = await this._request(
      `/api/v1/customer-services/${encodeURIComponent(instanceId)}/knowledge`,
    );
    return { items: page.items || [], total: page.total ?? 0 };
  }

  create(instanceId, payload) {
    return this._request(
      `/api/v1/customer-services/${encodeURIComponent(instanceId)}/knowledge`,
      {
        method: 'POST',
        body: JSON.stringify({ title: payload.title, body: payload.body }),
      },
    );
  }

  update(instanceId, documentId, payload) {
    return this._request(
      `/api/v1/customer-services/${encodeURIComponent(instanceId)}/knowledge/${encodeURIComponent(documentId)}`,
      {
        method: 'PUT',
        body: JSON.stringify({ title: payload.title, body: payload.body }),
      },
    );
  }

  async remove(instanceId, documentId) {
    await this._request(
      `/api/v1/customer-services/${encodeURIComponent(instanceId)}/knowledge/${encodeURIComponent(documentId)}`,
      { method: 'DELETE' },
    );
  }

  apply(instanceId, expectedVersion) {
    return this._request(
      `/api/v1/customer-services/${encodeURIComponent(instanceId)}/knowledge/apply`,
      {
        method: 'POST',
        body: JSON.stringify({ expected_version: expectedVersion }),
      },
    );
  }

  async _request(path, init = {}) {
    const response = await fetch(platformApiBase() + path, {
      ...init,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        ...platformAuthHeaders(),
        ...(init.headers || {}),
      },
    });
    if (response.status === 204) return null;
    if (response.status === 409) {
      throw new Error(CUSTOMER_SERVICE_VERSION_CONFLICT);
    }
    if (!response.ok) {
      throw new Error('平台服务暂时不可用，请稍后重试');
    }
    return response.json();
  }
}
