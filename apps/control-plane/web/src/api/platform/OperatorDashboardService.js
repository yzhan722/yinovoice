import { shellMockEnabled, operatorDashboardMock, tenantDashboardMock } from '@/mocks/shell';
import AdminDashboardEnum from '@/enum/AdminDashboardEnum';
import $WRequest from '@/utils/request/WRequest';

/** Platform Operator — dashboard (legacy: AdminDashboardService) */
export class OperatorDashboardService {
  getStats() {
    if (shellMockEnabled()) return Promise.resolve(operatorDashboardMock.stats);
    return $WRequest.postNoAnimation(AdminDashboardEnum.STATS, {});
  }

  getDailyChart(param = {}) {
    if (shellMockEnabled()) return Promise.resolve(operatorDashboardMock.dailyChart);
    return $WRequest.postNoAnimation(AdminDashboardEnum.DAILY_CHART, { ...param });
  }

  getMonthlyChart(param = {}) {
    if (shellMockEnabled()) return Promise.resolve(operatorDashboardMock.monthlyChart);
    return $WRequest.postNoAnimation(AdminDashboardEnum.MONTHLY_CHART, { ...param });
  }

  getCharts(param = {}) {
    if (shellMockEnabled()) return Promise.resolve(operatorDashboardMock.charts);
    return $WRequest.postNoAnimation(AdminDashboardEnum.CHARTS, { ...param });
  }
}

export { tenantDashboardMock };
