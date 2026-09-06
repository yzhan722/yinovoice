import { beforeEach, describe, expect, it, vi } from 'vitest';

const storeState = vi.hoisted(() => ({ roles: [] as string[] }));

vi.mock('@/store', () => ({
  useUserStore: () => ({ roles: storeState.roles }),
}));

import { getMenuList } from '@/api/permission';

import { PlatformAdminService } from './AdminService';
import {
  isActingAsOtherTenant,
  readHomeTenantId,
  readStoredTenantId,
  rememberSessionTenant,
  resetActingTenant,
  switchActingTenant,
} from './platformSession';

const TENANT_A = '00000000-0000-0000-0000-000000000001';
const TENANT_B = '00000000-0000-0000-0000-000000000002';

function jsonResponse(value: unknown, status = 200) {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(value),
  } as unknown as Response;
}

describe('platform admin menu gating', () => {
  it('hides the platform admin page from tenant operators', async () => {
    storeState.roles = ['tenant_operator'];
    const { list } = (await getMenuList('user')) as any;
    expect(list.find((menu: any) => menu.path === '/user/platform-admin')).toBeUndefined();
    expect(list.find((menu: any) => menu.path === '/user/assistant-settings')).toBeDefined();
  });

  it('shows the platform admin page to platform admins', async () => {
    storeState.roles = ['platform_admin'];
    const { list } = (await getMenuList('user')) as any;
    const admin = list.find((menu: any) => menu.path === '/user/platform-admin');
    expect(admin.meta.title).toEqual({ zh_CN: '平台管理', en_US: 'Platform Admin' });
    expect(admin.children[0].component).toBe('user/platform-admin/index');
  });
});

describe('acting tenant session', () => {
  beforeEach(() => sessionStorage.clear());

  it('pins tenant operators to their own tenant on every profile refresh', () => {
    switchActingTenant(TENANT_B);
    rememberSessionTenant(TENANT_A, ['tenant_operator']);
    expect(readStoredTenantId('')).toBe(TENANT_A);
    expect(readHomeTenantId()).toBe(TENANT_A);
    expect(isActingAsOtherTenant()).toBe(false);
  });

  it('lets platform admins keep a switched tenant and return home', () => {
    rememberSessionTenant(TENANT_A, ['platform_admin']);
    switchActingTenant(TENANT_B);
    rememberSessionTenant(TENANT_A, ['platform_admin']);
    expect(readStoredTenantId('')).toBe(TENANT_B);
    expect(isActingAsOtherTenant()).toBe(true);
    resetActingTenant();
    expect(readStoredTenantId('')).toBe(TENANT_A);
    expect(isActingAsOtherTenant()).toBe(false);
  });
});

describe('PlatformAdminService', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem(
      'userToken',
      JSON.stringify({ token: 'head.sig', expireTime: Date.now() + 60_000 }),
    );
    vi.stubGlobal('fetch', vi.fn());
  });

  it('calls the admin endpoints with the bearer token only', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ items: [{ id: TENANT_A, name: 'A' }], total: 1 }))
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_B, name: 'B' }, 201))
      .mockResolvedValueOnce(jsonResponse({ items: [], total: 0 }))
      .mockResolvedValueOnce(jsonResponse({ id: 'u1', account: 'ops' }, 201))
      .mockResolvedValueOnce({ ok: true, status: 204 } as Response)
      .mockResolvedValueOnce(jsonResponse({ id: 'u1', status: 'disabled' }));

    const service = new PlatformAdminService();
    expect(await service.listTenants()).toEqual([{ id: TENANT_A, name: 'A' }]);
    await service.createTenant({ name: 'B', homeRegion: 'ap-southeast' });
    expect(await service.listUsers(TENANT_B)).toEqual([]);
    await service.createUser({ tenantId: TENANT_B, account: 'ops', password: 'secret-1' });
    expect(await service.resetPassword('u1', 'rotated-1')).toBeNull();
    await service.setStatus('u1', 'disabled');

    const calls = fetchMock.mock.calls.map(([url, init]) => [
      String(url).replace(/^https?:\/\/[^/]+/, ''),
      init?.method || 'GET',
      init?.body ? JSON.parse(init.body) : undefined,
    ]);
    expect(calls).toEqual([
      ['/api/v1/admin/tenants', 'GET', undefined],
      ['/api/v1/admin/tenants', 'POST', { name: 'B', home_region: 'ap-southeast' }],
      [`/api/v1/admin/users?tenant_id=${TENANT_B}`, 'GET', undefined],
      [
        '/api/v1/admin/users',
        'POST',
        { tenant_id: TENANT_B, account: 'ops', password: 'secret-1', nickname: '', role: 'tenant_operator' },
      ],
      ['/api/v1/admin/users/u1/password', 'POST', { password: 'rotated-1' }],
      ['/api/v1/admin/users/u1/status', 'POST', { status: 'disabled' }],
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init.headers.Authorization).toBe('Bearer head.sig');
      expect(init.headers['X-Tenant-ID']).toBeUndefined();
    }
  });

  it('maps permission and conflict errors to readable messages', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: 'platform admin required' }, 403))
      .mockResolvedValueOnce(jsonResponse({ detail: 'account already exists' }, 409));
    const service = new PlatformAdminService();
    await expect(service.listTenants()).rejects.toThrow('需要平台管理员权限');
    await expect(
      service.createUser({ tenantId: TENANT_A, account: 'dup', password: 'secret-1' }),
    ).rejects.toThrow('account already exists');
  });
});
