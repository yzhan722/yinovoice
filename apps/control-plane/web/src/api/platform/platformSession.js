export const YINO_TENANT_STORAGE_KEY = 'yinoTenantId';

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
