import { BASE_API } from '@/config/api';

/**
 * 用户 Dashboard 独立接口，仅当前用户数据
 * - STATS: POST {} -> { outbound, inbound, totalMinutes }
 * - DAILY_CHART: POST { startedAtFrom?, startedAtTo? } 默认近1月、补0 -> { daily }
 * - MONTHLY_CHART: POST { startedAtFrom?, startedAtTo? } 默认近12月、补0 -> { monthly }
 * - CHARTS: POST { startedAtFrom?, startedAtTo? } -> { inbound, outbound, durationTrend }（补0）
 */
export default {
  STATS: BASE_API + 'api/user/dashboard/stats',
  DAILY_CHART: BASE_API + 'api/user/dashboard/daily-chart',
  MONTHLY_CHART: BASE_API + 'api/user/dashboard/monthly-chart',
  CHARTS: BASE_API + 'api/user/dashboard/charts',
};
