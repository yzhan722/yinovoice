import { BASE_API } from '@/config/api';

/**
 * 管理员 Dashboard 独立接口
 * - STATS: POST {} -> { userCount, assistantCount, outbound, inbound, totalMinutes }
 * - DAILY_CHART: POST { startedAtFrom?, startedAtTo? } 默认近1月、补0 -> { daily: [{date,count}] }
 * - MONTHLY_CHART: POST { startedAtFrom?, startedAtTo? } 默认近12月、补0 -> { monthly: [{month,count}] }
 * - CHARTS: POST { startedAtFrom?, startedAtTo? } -> { inbound, outbound, durationTrend }（补0）
 */
export default {
  STATS: BASE_API + 'api/admin/dashboard/stats',
  DAILY_CHART: BASE_API + 'api/admin/dashboard/daily-chart',
  MONTHLY_CHART: BASE_API + 'api/admin/dashboard/monthly-chart',
  CHARTS: BASE_API + 'api/admin/dashboard/charts',
};
