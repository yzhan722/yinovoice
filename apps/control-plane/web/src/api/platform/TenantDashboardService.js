import { shellMockEnabled, tenantDashboardMock } from '@/mocks/shell';
import UserDashboardEnum from '@/enum/UserDashboardEnum';
import $WRequest from '@/utils/request/WRequest';

/** Tenant — dashboard (legacy: UserDashboardService) */
export class TenantDashboardService {
  getStats() {
    if (shellMockEnabled()) return Promise.resolve(tenantDashboardMock.stats);
    return $WRequest.postNoAnimation(UserDashboardEnum.STATS, {});
  }

  getDailyChart(param = {}) {
    if (shellMockEnabled()) return Promise.resolve(tenantDashboardMock.dailyChart);
    return $WRequest.postNoAnimation(UserDashboardEnum.DAILY_CHART, { ...param });
  }

  getMonthlyChart(param = {}) {
    if (shellMockEnabled()) return Promise.resolve(tenantDashboardMock.monthlyChart);
    return $WRequest.postNoAnimation(UserDashboardEnum.MONTHLY_CHART, { ...param });
  }

  getCharts(param = {}) {
    if (shellMockEnabled()) return Promise.resolve(tenantDashboardMock.charts);
    return $WRequest.postNoAnimation(UserDashboardEnum.CHARTS, { ...param });
  }
}
