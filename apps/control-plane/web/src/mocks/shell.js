/** Shell-local Platform Core fixtures. Enabled when VITE_SHELL_MOCK=true */

export function shellMockEnabled() {
  return String(import.meta.env.VITE_SHELL_MOCK || '').toLowerCase() === 'true';
}

/**
 * Flip on after the call-system project is shared and wired.
 * See apps/admin/docs/CALL_INTEGRATION.md
 */
export function callSystemReady() {
  return String(import.meta.env.VITE_CALL_SYSTEM_READY || '').toLowerCase() === 'true';
}

/** Demo accounts for shell UI walkthrough (no backend). */
export const SHELL_ACCOUNTS = {
  tenant: {
    account: 'demo',
    password: 'demo123',
    nickname: '太平洋口腔',
  },
  operator: {
    account: 'admin',
    password: 'admin123',
    nickname: 'Platform Operator',
  },
};

export function shellLogin(role, account, password) {
  const expected = role === 'operator' ? SHELL_ACCOUNTS.operator : SHELL_ACCOUNTS.tenant;
  if (account !== expected.account || password !== expected.password) {
    const err = new Error('账号或密码错误（壳模式测试账号见登录页提示）');
    err.code = 401;
    throw err;
  }
  const tokenExpireTime = Date.now() + 24 * 60 * 60 * 1000;
  if (role === 'operator') {
    return {
      token: 'shell-operator-token',
      tokenExpireTime,
      account: expected.account,
    };
  }
  return {
    token: 'shell-tenant-token',
    tokenExpireTime,
    account: expected.account,
    userAccount: expected.account,
    userNickname: expected.nickname,
  };
}

export function shellTenantProfile() {
  const a = SHELL_ACCOUNTS.tenant;
  return {
    userAccount: a.account,
    userNickname: a.nickname,
    userCompanyName: '常州太平洋口腔',
    name: a.nickname,
    roles: ['all'],
    permissions: [],
  };
}

export function shellOperatorProfile() {
  return {
    account: SHELL_ACCOUNTS.operator.account,
  };
}

function lastNDays(n, seed = 3) {
  const out = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i -= 1) {
    const d = new Date(now);
    d.setDate(now.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    out.push({
      date: key,
      count: seed + (i % 5) + (i % 3),
      minutes: 10 + (i % 7) * 4,
    });
  }
  return out;
}

function lastNMonths(n, seed = 20) {
  const out = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i -= 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    out.push({
      month: key,
      count: seed + i * 2,
      minutes: 120 + i * 15,
    });
  }
  return out;
}

const operatorDaily = lastNDays(30);
const operatorMonthly = lastNMonths(12);
const tenantDaily = lastNDays(30, 1);
const tenantMonthly = lastNMonths(12, 8);

export const operatorDashboardMock = {
  stats: {
    userCount: 12,
    assistantCount: 28,
    outbound: 146,
    inbound: 392,
    totalMinutes: 1840,
  },
  dailyChart: {
    daily: operatorDaily.map(({ date, count }) => ({ date, count })),
  },
  monthlyChart: {
    monthly: operatorMonthly.map(({ month, count }) => ({ month, count })),
    durationTrend: operatorMonthly.map(({ month, minutes }) => ({ month, minutes })),
  },
  charts: {
    inbound: 392,
    outbound: 146,
    durationTrend: operatorDaily.map(({ date, minutes }) => ({ date, minutes })),
  },
};

export const tenantDashboardMock = {
  stats: {
    outbound: 24,
    inbound: 67,
    totalMinutes: 210,
  },
  dailyChart: {
    daily: tenantDaily.map(({ date, count }) => ({ date, count })),
  },
  monthlyChart: {
    monthly: tenantMonthly.map(({ month, count }) => ({ month, count })),
    durationTrend: tenantMonthly.map(({ month, minutes }) => ({ month, minutes })),
  },
  charts: {
    inbound: 67,
    outbound: 24,
    durationTrend: tenantDaily.map(({ date, minutes }) => ({ date, minutes })),
  },
};
