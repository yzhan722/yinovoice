export const YINO_TENANT_STORAGE_KEY = 'yinoTenantId';
// Tenant the account belongs to. `yinoTenantId` is the tenant currently being
// operated: identical for tenant operators, switchable for platform admins.
export const YINO_HOME_TENANT_STORAGE_KEY = 'yinoHomeTenantId';
export const PLATFORM_ADMIN_ROLE = 'platform_admin';

const FALLBACK_TENANT_ID = '00000000-0000-0000-0000-000000000001';

export function platformApiBase() {
  return String(import.meta.env.VITE_PLATFORM_API_BASE || 'http://localhost:8000').replace(
    /\/+$/,
    '',
  );
}

export function readStoredUserToken() {
  if (typeof sessionStorage === 'undefined') return '';
  try {
    const raw = sessionStorage.getItem('userToken');
    if (!raw) return '';
    const data = JSON.parse(raw);
    if (data.expireTime && data.expireTime <= Date.now()) return '';
    return data.token || '';
  } catch {
    return '';
  }
}

export function readStoredTenantId(fallback = FALLBACK_TENANT_ID) {
  if (typeof sessionStorage === 'undefined') return fallback;
  try {
    return sessionStorage.getItem(YINO_TENANT_STORAGE_KEY) || fallback;
  } catch {
    return fallback;
  }
}

export function storeTenantId(tenantId) {
  if (!tenantId || typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(YINO_TENANT_STORAGE_KEY, String(tenantId));
}

export function clearStoredTenantId() {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(YINO_TENANT_STORAGE_KEY);
  sessionStorage.removeItem(YINO_HOME_TENANT_STORAGE_KEY);
}

export function readHomeTenantId() {
  if (typeof sessionStorage === 'undefined') return '';
  try {
    return sessionStorage.getItem(YINO_HOME_TENANT_STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

/**
 * Record the account's own tenant after login / profile refresh. Platform
 * admins keep whatever tenant they switched to; everyone else is pinned.
 */
export function rememberSessionTenant(tenantId, roles = []) {
  if (!tenantId || typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(YINO_HOME_TENANT_STORAGE_KEY, String(tenantId));
  const isAdmin = Array.isArray(roles) && roles.includes(PLATFORM_ADMIN_ROLE);
  if (!isAdmin || !readStoredTenantId('')) {
    storeTenantId(tenantId);
  }
}

export function switchActingTenant(tenantId) {
  storeTenantId(tenantId);
}

export function resetActingTenant() {
  const home = readHomeTenantId();
  if (home) storeTenantId(home);
}

export function isActingAsOtherTenant() {
  const home = readHomeTenantId();
  return Boolean(home) && readStoredTenantId('') !== home;
}

export function platformAuthHeaders(fallbackTenant = FALLBACK_TENANT_ID) {
  const headers = {
    'X-Tenant-ID': readStoredTenantId(fallbackTenant),
  };
  const token = readStoredUserToken();
  if (token && token.includes('.')) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}
