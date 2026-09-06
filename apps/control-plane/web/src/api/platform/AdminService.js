import { platformApiBase, readStoredUserToken } from './platformSession';

/**
 * Platform-admin endpoints (/api/v1/admin/*). These are account-scoped, not
 * tenant-scoped, so only the bearer token is sent.
 */
async function adminRequest(path, init = {}) {
  const token = readStoredUserToken();
  const response = await fetch(platformApiBase() + path, {
    ...init,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    if (response.status === 401) throw new Error('登录已失效，请重新登录');
    if (response.status === 403) throw new Error('需要平台管理员权限');
    if (response.status === 404) throw new Error(detail || '对象不存在');
    if (response.status === 409) throw new Error(detail || '已存在或状态冲突');
    if (response.status === 422) throw new Error('输入不合法，请检查后重试');
    throw new Error(detail || '平台服务暂时不可用，请稍后重试');
  }
  return response.json();
}

export class PlatformAdminService {
  async listTenants() {
    const page = await adminRequest('/api/v1/admin/tenants');
    return page?.items || [];
  }

  /** @param {{ name: string, homeRegion?: string, id?: string }} input */
  createTenant({ name, homeRegion, id }) {
    return adminRequest('/api/v1/admin/tenants', {
      method: 'POST',
      body: JSON.stringify({
        name,
        home_region: homeRegion || 'cn-mainland',
        ...(id ? { id } : {}),
      }),
    });
  }

  async listUsers(tenantId) {
    const qs = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : '';
    const page = await adminRequest(`/api/v1/admin/users${qs}`);
    return page?.items || [];
  }

  /**
   * @param {{ tenantId: string, account: string, password: string,
   *           nickname?: string, role?: string }} input
   */
  createUser({ tenantId, account, password, nickname, role }) {
    return adminRequest('/api/v1/admin/users', {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: tenantId,
        account,
        password,
        nickname: nickname || '',
        role: role || 'tenant_operator',
      }),
    });
  }

  resetPassword(userId, password) {
    return adminRequest(`/api/v1/admin/users/${encodeURIComponent(userId)}/password`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    });
  }

  setStatus(userId, status) {
    return adminRequest(`/api/v1/admin/users/${encodeURIComponent(userId)}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    });
  }
}
