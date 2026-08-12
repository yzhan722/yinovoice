<template>
  <div class="home">
    <header class="top-row">
      <div class="greet-block">
        <p class="hello">{{ greeting }}，{{ userName }}</p>
        <h1 class="headline">今日语音前台工作台</h1>
      </div>
      <div class="top-tools">
        <label class="search">
          <t-icon name="search" />
          <input v-model="q" type="search" placeholder="搜索回拨、预约、通话…" />
        </label>
        <button type="button" class="bell" aria-label="通知" @click="go('/user/callback-tasks')">
          <t-icon name="notification" />
          <span v-if="summary.callbacks.open" class="badge">{{ summary.callbacks.open }}</span>
        </button>
      </div>
    </header>

    <section class="kpi-grid">
      <button type="button" class="kpi" @click="go('/user/callback-tasks')">
        <div class="kpi-ico indigo"><t-icon name="task" /></div>
        <div>
          <div class="kpi-label">待处理回拨</div>
          <div class="kpi-num">{{ summary.callbacks.open }}</div>
        </div>
      </button>
      <button type="button" class="kpi" @click="go('/user/appointments')">
        <div class="kpi-ico sky"><t-icon name="calendar" /></div>
        <div>
          <div class="kpi-label">今日预约</div>
          <div class="kpi-num">{{ summary.appointments.today }}</div>
        </div>
      </button>
      <button type="button" class="kpi" @click="go('/user/appointments')">
        <div class="kpi-ico amber"><t-icon name="error-circle" /></div>
        <div>
          <div class="kpi-label">待确认</div>
          <div class="kpi-num">{{ summary.appointments.pendingConfirm }}</div>
        </div>
      </button>
      <button type="button" class="kpi" @click="go('/user/call-history')">
        <div class="kpi-ico green"><t-icon name="call" /></div>
        <div>
          <div class="kpi-label">接通率</div>
          <div class="kpi-num">{{ connectRate }}%</div>
        </div>
      </button>
    </section>

    <div class="board">
      <section class="card schedule-card">
        <div class="card-head">
          <h2>今日日程</h2>
          <button type="button" class="text-link" @click="go('/user/planner')">查看计划</button>
        </div>
        <ul class="schedule">
          <li v-for="item in scheduleItems" :key="item.id">
            <div class="when">
              <strong>{{ item.time }}</strong>
              <span>{{ item.tag }}</span>
            </div>
            <div class="body">
              <div class="title">{{ item.title }}</div>
              <div class="sub">{{ item.sub }}</div>
            </div>
            <span v-if="item.live" class="live">进行中</span>
          </li>
          <li v-if="!scheduleItems.length" class="empty">暂无今日事项</li>
        </ul>
      </section>

      <div class="right-col">
        <section class="card progress-card">
          <div class="card-head"><h2>学习进度</h2><span class="muted">整体完成度</span></div>
          <div class="progress-wrap">
            <div class="donut">
              <svg viewBox="0 0 36 36">
                <path class="bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                <path
                  class="fg"
                  :stroke-dasharray="`${overallProgress}, 100`"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <div class="donut-label">
                <strong>{{ overallProgress }}%</strong>
                <span>Overall</span>
              </div>
            </div>
            <ul class="legend">
              <li><i class="done" />已完成 {{ summary.followUps.done }}</li>
              <li><i class="doing" />进行中 {{ summary.followUps.doing }}</li>
              <li><i class="todo" />未开始 {{ summary.followUps.todo }}</li>
            </ul>
          </div>
        </section>

        <section class="card goals-card">
          <div class="card-head"><h2>工作目标</h2></div>
          <div v-for="g in goals" :key="g.name" class="goal">
            <div class="goal-top">
              <span>{{ g.name }}</span>
              <strong>{{ g.pct }}%</strong>
            </div>
            <div class="bar"><span :style="{ width: `${g.pct}%`, background: g.color }" /></div>
          </div>
        </section>

        <section class="streak" @click="go('/user/celebration')">
          <div>
            <div class="streak-label">Current Streak</div>
            <div class="streak-value">{{ streakDays }} Days</div>
            <div class="streak-desc">连续处理跟进 · 点击庆祝</div>
          </div>
          <div class="flame">🔥</div>
        </section>
      </div>
    </div>

    <section class="card chart-card">
      <div class="card-head">
        <h2>表现概览</h2>
        <span class="muted">近 7 日通话 · 演示</span>
      </div>
      <EchartsChart :option="trendOption" height="220px" />
    </section>

    <!-- Mobile home extras -->
    <section class="mobile-only continue-card" @click="go('/user/callback-tasks')">
      <div class="continue-kicker">Continue Learning</div>
      <div class="continue-title">继续处理待回拨</div>
      <div class="continue-sub">{{ summary.callbacks.open }} 条待处理 · 点此进入</div>
      <div class="continue-bar"><span :style="{ width: `${Math.min(100, connectRate)}%` }" /></div>
    </section>

    <section class="mobile-only courses-card">
      <div class="card-head">
        <h2>我的课程</h2>
        <button type="button" class="text-link" @click="go('/user/appointments')">全部</button>
      </div>
      <button
        v-for="c in mobileCourses"
        :key="c.id"
        type="button"
        class="course-row"
        @click="go(c.path)"
      >
        <div class="course-ico" :style="{ background: c.bg, color: c.fg }"><t-icon :name="c.icon" /></div>
        <div class="course-body">
          <div class="course-title">{{ c.title }}</div>
          <div class="course-sub">{{ c.sub }}</div>
        </div>
        <t-icon name="chevron-right" />
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import EchartsChart from '@/components/echarts-chart/index.vue';
import { TenantHomeService } from '@/api/platform';
import { useUserStore } from '@/store';

const router = useRouter();
const user = useUserStore();
const homeSvc = new TenantHomeService();
const q = ref('');

const hour = new Date().getHours();
const greeting = hour < 12 ? 'Good Morning' : hour < 18 ? 'Good Afternoon' : 'Good Evening';
const userName = computed(() => user.userInfo?.name || user.userInfo?.nickname || '太平洋口腔');

const summary = reactive({
  callbacks: { open: 0, delta: 0 },
  appointments: { today: 0, week: 0, pendingConfirm: 0 },
  followUps: { todo: 0, doing: 0, done: 0 },
});

const callStats = reactive({
  todayCount: 0,
  connectedToday: 0,
  effectiveToday: 0,
  todayMinutes: 0,
  trend: [] as { date: string; count: number; minutes: number }[],
});

const followUps = ref<any[]>([]);
const appointments = ref<any[]>([]);

const connectRate = computed(() => {
  const t = callStats.todayCount || 0;
  if (!t) return 72;
  return Math.min(100, Math.round((callStats.connectedToday / t) * 100));
});

const overallProgress = computed(() => {
  const total =
    summary.followUps.todo + summary.followUps.doing + summary.followUps.done || 1;
  return Math.min(100, Math.round((summary.followUps.done / total) * 100) || 72);
});

const streakDays = computed(() => Math.max(3, summary.followUps.done + 8));

const goals = computed(() => [
  { name: '回拨闭环', pct: Math.min(100, 40 + summary.callbacks.open * 5), color: '#5B4DFF' },
  { name: '预约确认', pct: Math.min(100, 55 + summary.appointments.pendingConfirm * 8), color: '#38BDF8' },
  { name: '知识库更新', pct: 64, color: '#22C55E' },
]);

const scheduleItems = computed(() => {
  const fromFollow = followUps.value.slice(0, 4).map((f, i) => ({
    id: f.id,
    time: ['09:00', '11:30', '14:00', '16:30'][i] || '10:00',
    tag: ({ todo: '待办', doing: '进行中', done: '完成' } as any)[f.status] || '事项',
    title: f.title,
    sub: '跟进事项 · 太平洋口腔',
    live: f.status === 'doing',
  }));
  if (fromFollow.length) return fromFollow;
  return [
    { id: 1, time: '09:30', tag: '预约', title: '种植咨询确认', sub: '新北旗舰店 · 张医生', live: true },
    { id: 2, time: '11:00', tag: '回拨', title: '未接通回访', sub: '来电 138****6521', live: false },
    { id: 3, time: '15:00', tag: '直播班', title: '语音接待巡检', sub: '实例 · 新北前台', live: false },
  ];
});

const mobileCourses = computed(() => [
  {
    id: 1,
    title: '回拨任务',
    sub: `${summary.callbacks.open} 待处理`,
    path: '/user/callback-tasks',
    icon: 'task',
    bg: '#EEF0FF',
    fg: '#5B4DFF',
  },
  {
    id: 2,
    title: '预约结果',
    sub: `今日 ${summary.appointments.today} 场`,
    path: '/user/appointments',
    icon: 'calendar',
    bg: '#E0F2FE',
    fg: '#0284C7',
  },
  {
    id: 3,
    title: '成就徽章',
    sub: '查看本周成就',
    path: '/user/achievements',
    icon: 'secured',
    bg: '#FEF3C7',
    fg: '#D97706',
  },
]);

const trendOption = computed(() => {
  const trend = callStats.trend || [];
  return {
    grid: { left: 36, right: 12, top: 24, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: trend.map((x) => x.date.slice(5)),
      axisLabel: { color: '#6b7280', fontSize: 11 },
      axisLine: { lineStyle: { color: '#e8e9f2' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#e8e9f2', type: 'dashed' } },
      axisLabel: { color: '#6b7280', fontSize: 11 },
    },
    series: [
      {
        name: '通话',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: trend.map((x) => x.count),
        lineStyle: { width: 3, color: '#5B4DFF' },
        itemStyle: { color: '#5B4DFF' },
        areaStyle: { color: 'rgba(91,77,255,0.12)' },
      },
    ],
  };
});

function go(path: string) {
  router.push(path);
}

async function refreshHome() {
  try {
    const s: any = await homeSvc.summary();
    Object.assign(summary.callbacks, s.callbacks || {});
    Object.assign(summary.appointments, s.appointments || {});
    Object.assign(summary.followUps, s.followUps || {});
    if (s.callStats) Object.assign(callStats, s.callStats);
  } catch (_) {}
  try {
    const fu: any = await homeSvc.followUps();
    followUps.value = (fu?.list || []).filter((x: any) => x.status !== 'done').slice(0, 6);
  } catch (_) {
    followUps.value = [];
  }
  try {
    const ap: any = await homeSvc.appointmentsToday?.();
    appointments.value = ap?.list || [];
  } catch (_) {}
}

onMounted(refreshHome);
</script>

<style scoped lang="less">
.home {
  max-width: 1180px;
  margin: 0 auto;
  padding: 4px 4px 36px;
  font-family: var(--demo-font);
}

.top-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.hello {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--demo-muted);
}

.headline {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--demo-ink);
}

.top-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 240px;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid var(--demo-line);
  border-radius: 999px;
  box-shadow: var(--demo-shadow);
  color: var(--demo-muted);

  input {
    border: 0;
    outline: 0;
    width: 100%;
    font: inherit;
    font-size: 13px;
    background: transparent;
  }
}

.bell {
  position: relative;
  width: 42px;
  height: 42px;
  border: 1px solid var(--demo-line);
  border-radius: 14px;
  background: #fff;
  cursor: pointer;
  color: var(--demo-ink);

  .badge {
    position: absolute;
    top: -4px;
    right: -4px;
    min-width: 18px;
    height: 18px;
    padding: 0 4px;
    border-radius: 999px;
    background: #ef4444;
    color: #fff;
    font-size: 10px;
    font-weight: 800;
    display: grid;
    place-items: center;
  }
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.kpi {
  display: flex;
  gap: 12px;
  align-items: center;
  text-align: left;
  padding: 16px;
  border: 1px solid var(--demo-line);
  border-radius: var(--demo-radius);
  background: #fff;
  box-shadow: var(--demo-shadow);
  cursor: pointer;
  font-family: inherit;
}

.kpi-ico {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-size: 20px;
  &.indigo { background: #eef0ff; color: #5b4dff; }
  &.sky { background: #e0f2fe; color: #0284c7; }
  &.amber { background: #ffedd5; color: #ea580c; }
  &.green { background: #dcfce7; color: #16a34a; }
}

.kpi-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--demo-muted);
}

.kpi-num {
  margin-top: 2px;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--demo-ink);
}

.board {
  display: grid;
  grid-template-columns: 1.2fr 0.85fr;
  gap: 14px;
  margin-bottom: 14px;
}

.right-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card {
  background: #fff;
  border: 1px solid var(--demo-line);
  border-radius: var(--demo-radius);
  box-shadow: var(--demo-shadow);
  padding: 16px 18px;
}

.card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;

  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 800;
  }
}

.muted { font-size: 12px; color: var(--demo-muted); font-weight: 600; }
.text-link {
  border: 0;
  background: transparent;
  color: var(--demo-primary);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
}

.schedule {
  list-style: none;
  margin: 0;
  padding: 0;

  li {
    display: grid;
    grid-template-columns: 72px 1fr auto;
    gap: 12px;
    align-items: center;
    padding: 14px 0;
    border-top: 1px solid var(--demo-line);
    &:first-child { border-top: 0; padding-top: 0; }
  }
}

.when {
  display: flex;
  flex-direction: column;
  gap: 4px;
  strong { font-size: 13px; }
  span { font-size: 11px; color: var(--demo-muted); font-weight: 600; }
}

.body .title { font-size: 14px; font-weight: 700; }
.body .sub { margin-top: 4px; font-size: 12px; color: var(--demo-muted); }

.live {
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef0ff;
  color: var(--demo-primary);
  font-size: 11px;
  font-weight: 800;
}

.empty { color: var(--demo-muted); font-size: 13px; padding: 12px 0; }

.progress-wrap {
  display: flex;
  gap: 18px;
  align-items: center;
}

.donut {
  position: relative;
  width: 110px;
  height: 110px;
  flex-shrink: 0;

  svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .bg { fill: none; stroke: #eceef8; stroke-width: 3.2; }
  .fg { fill: none; stroke: #5b4dff; stroke-width: 3.2; stroke-linecap: round; }
}

.donut-label {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  text-align: center;
  strong { font-size: 20px; font-weight: 800; display: block; }
  span { font-size: 10px; color: var(--demo-muted); }
}

.legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--demo-muted);

  i {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 8px;
    &.done { background: #22c55e; }
    &.doing { background: #5b4dff; }
    &.todo { background: #cbd5e1; }
  }
}

.goal + .goal { margin-top: 12px; }
.goal-top {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}
.bar {
  height: 8px;
  border-radius: 999px;
  background: #eceef8;
  overflow: hidden;
  span { display: block; height: 100%; border-radius: inherit; }
}

.streak {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-radius: var(--demo-radius);
  background: linear-gradient(135deg, #5b4dff 0%, #7c3aed 100%);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 12px 28px rgba(91, 77, 255, 0.28);
}
.streak-label { font-size: 12px; opacity: 0.9; font-weight: 600; }
.streak-value { margin-top: 4px; font-size: 34px; font-weight: 800; letter-spacing: -0.03em; }
.streak-desc { margin-top: 6px; font-size: 12px; opacity: 0.85; }
.flame { font-size: 40px; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.15)); }

.chart-card { margin-bottom: 14px; }

.mobile-only { display: none; }

.continue-card {
  padding: 18px;
  border-radius: var(--demo-radius);
  background: linear-gradient(135deg, #5b4dff, #818cf8);
  color: #fff;
  margin-bottom: 12px;
  cursor: pointer;
}
.continue-kicker { font-size: 12px; opacity: 0.9; font-weight: 600; }
.continue-title { margin-top: 6px; font-size: 20px; font-weight: 800; }
.continue-sub { margin-top: 4px; font-size: 12px; opacity: 0.9; }
.continue-bar {
  margin-top: 14px;
  height: 6px;
  border-radius: 999px;
  background: rgba(255,255,255,0.28);
  overflow: hidden;
  span { display: block; height: 100%; background: #fff; }
}

.course-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border: 0;
  border-top: 1px solid var(--demo-line);
  background: transparent;
  text-align: left;
  cursor: pointer;
  font-family: inherit;
  color: inherit;
  &:first-of-type { border-top: 0; }
}
.course-ico {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-size: 18px;
}
.course-title { font-size: 14px; font-weight: 700; }
.course-sub { font-size: 12px; color: var(--demo-muted); margin-top: 2px; }

@media (max-width: 960px) {
  .board { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 768px) {
  .headline { font-size: 22px; }
  .search { min-width: 0; flex: 1; }
  .chart-card, .schedule-card, .progress-card, .goals-card { display: none; }
  .mobile-only { display: block; }
  .courses-card {
    display: block;
    background: #fff;
    border: 1px solid var(--demo-line);
    border-radius: var(--demo-radius);
    box-shadow: var(--demo-shadow);
    padding: 14px 16px;
  }
  .board { display: block; }
  .right-col .streak { margin-top: 12px; }
  .right-col .progress-card,
  .right-col .goals-card { display: none; }
}
</style>
