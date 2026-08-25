import { shellMockEnabled, shellLogin, shellTenantProfile } from '@/mocks/shell';
import { DEMO_TENANT_ID } from './platform/RealtimeVoiceService';
import {
  clearStoredTenantId,
  platformApiBase,
  readStoredUserToken,
  storeTenantId,
} from './platform/platformSession';

export class UserBasicService {
  /** Tenant login: Platform /api/v1/auth/login (shell mock keeps local demo). */
  login(param) {
    if (shellMockEnabled()) {
      const result = shellLogin('tenant', param?.account, param?.password);
      storeTenantId(DEMO_TENANT_ID);
      return Promise.resolve(result);
    }
    return this._platformLogin(param?.account, param?.password);
  }

  getUserInfo(param) {
    if (shellMockEnabled()) {
      return Promise.resolve(shellTenantProfile());
    }
    return this._platformMe();
  }

  logout() {
    clearStoredTenantId();
    if (shellMockEnabled()) {
      return Promise.resolve({ ok: true });
    }
    return Promise.resolve({ ok: true });
  }

  getAccessToken() {
    const token = readStoredUserToken();
    return Promise.resolve({ accessToken: token || 'shell-access-token' });
  }

  async _platformLogin(account, password) {
    const response = await fetch(`${platformApiBase()}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account, password }),
    });
    if (response.status === 401) {
      const err = new Error('账号或密码错误');
      err.code = 401;
      throw err;
    }
    if (!response.ok) {
      throw new Error('登录失败');
    }
    const body = await response.json();
    storeTenantId(body.tenant_id);
    return body;
  }

  async _platformMe() {
    const token = readStoredUserToken();
    if (!token) {
      throw new Error('未登录');
    }
    const response = await fetch(`${platformApiBase()}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new Error('登录已失效');
    }
    const body = await response.json();
    storeTenantId(body.tenant_id);
    return {
      userAccount: body.userAccount || body.account,
      userNickname: body.userNickname || body.account,
      name: body.userNickname || body.account,
      roles: body.roles?.length ? body.roles : ['all'],
      permissions: [],
      tenant_id: body.tenant_id,
    };
  }
}
