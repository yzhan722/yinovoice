<template>
  <div class="home">
    <header class="top-row">
      <div class="greet-block">
        <p class="hello">{{ greeting }}，{{ userName }}</p>
        <h1 class="headline">工作台</h1>
        <p class="subhead">今日语音前台运营概览</p>
      </div>
      <div class="top-tools">
        <label class="search">
          <t-icon name="search" />
          <input v-model="q" type="search" placeholder="搜索回拨、预约、通话…" />
        </label>
        <button type="button" class="bell" aria-label="待处理回拨" @click="go('/user/callback-tasks')">
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
          <div class="kpi-label">待确认预约</div>
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

    <section class="quick-row">
      <button type="button" class="quick" @click="go('/user/realtime-voice')">
        <t-icon name="sound" />
        <span>开始实时通话</span>
      </button>
      <button type="button" class="quick" @click="go('/user/call-history')">
        <t-icon name="history" />
        <span>通话记录</span>
      </button>
      <button type="button" class="quick" @click="go('/user/appointments')">
        <t-icon name="calendar" />
        <span>预约结果</span>
      </button>
      <button type="button" class="quick" @click="go('/user/callback-tasks')">
        <t-icon name="call" />
        <span>回拨任务</span>
      </button>
      <button type="button" class="quick" @click="go('/user/telephony')">
        <t-icon name="call-1" />
        <span>电话号码</span>
      </button>
      <button type="button" class="quick" @click="go('/user/scheduling')">
        <t-icon name="time" />
        <span>排期设置</span>
      </button>
    </section>

    <div class="board">
      <section class="card schedule-card">
        <div class="card-head">
          <h2>今日待办</h2>
          <button type="button" class="text-link" @click="go('/user/callback-tasks')">查看全部</button>
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
          <li v-if="!scheduleItems.length" class="empty">暂无今日待办</li>
        </ul>
      </section>

      <div class="right-col">
        <section class="card progress-card">
          <div class="card-head">
            <h2>跟进进度</h2>
            <span class="muted">整体完成度</span>
          </div>
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
                <span>完成</span>
              </div>
            </div>
            <ul class="legend">
              <li><i class="done" />已完成 {{ summary.followUps.done }}</li>
              <li><i class="doing" />进行中 {{ summary.followUps.doing }}</li>
              <li><i class="todo" />未开始 {{ summary.followUps.todo }}</li>
            </ul>
          </div>
        </section>

        <section class="card ops-card">
          <div class="card-head"><h2>运营摘要</h2></div>
          <ul class="ops-list">
            <li>
              <span>待确认预约</span>
              <strong>{{ summary.appointments.pendingConfirm }}</strong>
            </li>
            <li>
              <span>开放回拨</span>
              <strong>{{ summary.callbacks.open }}</strong>
            </li>
            <li>
              <span>今日通话</span>
              <strong>{{ callStats.todayCount || '—' }}</strong>
            </li>
          </ul>
        </section>
      </div>
    </div>

    <section class="card chart-card">
      <div class="card-head">
        <h2>近 7 日通话量</h2>
        <span class="muted">近 7 日</span>
      </div>
      <EchartsChart :option="trendOption" height="220px" />
    </section>

    <section class="mobile-only continue-card" @click="go('/user/callback-tasks')">
      <div class="continue-kicker">待处理</div>
      <div class="continue-title">继续处理回拨任务</div>
      <div class="continue-sub">{{ summary.callbacks.open }} 条待处理</div>
    </section>

    <section class="mobile-only courses-card">
      <div class="card-head">
        <h2>快捷入口</h2>
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
const greeting = hour < 12 ? '上午好' : hour < 18 ? '下午好' : '晚上好';
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

const connectRate = computed(() => {
  const t = callStats.todayCount || 0;
  if (!t) return 0;
  return Math.min(100, Math.round((callStats.connectedToday / t) * 100));
});

const overallProgress = computed(() => {
  const total =
    summary.followUps.todo + summary.followUps.doing + summary.followUps.done;
  if (!total) return 0;
  return Math.min(100, Math.round((summary.followUps.done / total) * 100));
});

const scheduleItems = computed(() => (
  followUps.value.slice(0, 4).map((f, i) => ({
    id: f.id,
    time: ['09:00', '11:30', '14:00', '16:30'][i] || '10:00',
    tag: ({ todo: '待办', doing: '进行中', done: '完成' } as any)[f.status] || '事项',
    title: f.title,
    sub: '跟进事项',
    live: f.status === 'doing',
  }))
));

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
    title: '通话记录',
    sub: '查看转写与录音',
    path: '/user/call-history',
    icon: 'history',
    bg: '#ECFDF5',
    fg: '#059669',
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
        lineStyle: { width: 3, color: '#0052d9' },
        itemStyle: { color: '#0052d9' },
        areaStyle: { color: 'rgba(0,82,217,0.10)' },
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
}

.hello {
  margin: 0;
  color: var(--demo-muted);
  font-size: 13px;
  font-weight: 600;
}

.headline {
  margin: 4px 0 0;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--demo-ink);
}

.subhead {
  margin: 6px 0 0;
  color: var(--demo-muted);
  font-size: 13px;
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
  padding: 8px 12px;
  background: #fff;
  border: 1px solid var(--demo-line);
  border-radius: 10px;
  input {
    border: 0;
    outline: 0;
    width: 100%;
    background: transparent;
    font: inherit;
  }
}

.bell {
  position: relative;
  width: 40px;
  height: 40px;
  border: 1px solid var(--demo-line);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #d92d20;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.kpi {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  text-align: left;
  background: #fff;
  border: 1px solid var(--demo-line);
  border-radius: 14px;
  cursor: pointer;
}

.kpi-ico {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  &.indigo { background: #eef0ff; color: #4338ca; }
  &.sky { background: #e0f2fe; color: #0284c7; }
  &.amber { background: #fef3c7; color: #b45309; }
  &.green { background: #dcfce7; color: #15803d; }
}

.kpi-label { color: var(--demo-muted); font-size: 12px; font-weight: 600; }
.kpi-num { margin-top: 2px; font-size: 24px; font-weight: 800; }

.quick-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.quick {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  background: #fff;
  border: 1px solid var(--demo-line);
  border-radius: 10px;
  cursor: pointer;
  font-weight: 700;
  color: var(--demo-ink);
}

.board {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
  gap: 14px;
  margin-bottom: 14px;
}

.card {
  background: #fff;
  border: 1px solid var(--demo-line);
  border-radius: 14px;
  padding: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  h2 { margin: 0; font-size: 16px; font-weight: 800; }
}

.muted { color: var(--demo-muted); font-size: 12px; }
.text-link {
  border: 0;
  background: transparent;
  color: var(--demo-primary);
  font-weight: 700;
  cursor: pointer;
}

.schedule { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.schedule li {
  display: grid;
  grid-template-columns: 72px 1fr auto;
  gap: 10px;
  align-items: start;
  padding: 10px 0;
  border-bottom: 1px solid #f0f2f5;
}
.schedule li:last-child { border-bottom: 0; }
.when strong { display: block; font-size: 14px; }
.when span { color: var(--demo-muted); font-size: 11px; font-weight: 700; }
.title { font-weight: 700; }
.sub { margin-top: 2px; color: var(--demo-muted); font-size: 12px; }
.live {
  padding: 2px 8px;
  border-radius: 999px;
  background: #ecfdf5;
  color: #047857;
  font-size: 11px;
  font-weight: 700;
}
.empty { color: var(--demo-muted); padding: 18px 0; text-align: center; }

.right-col { display: grid; gap: 14px; }

.progress-wrap {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 12px;
  align-items: center;
}

.donut {
  position: relative;
  width: 110px;
  height: 110px;
  svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .bg { fill: none; stroke: #eef1f5; stroke-width: 3.2; }
  .fg { fill: none; stroke: #0052d9; stroke-width: 3.2; stroke-linecap: round; }
}

.donut-label {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  text-align: center;
  strong { font-size: 20px; }
  span { color: var(--demo-muted); font-size: 11px; }
}

.legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
  font-size: 13px;
  i {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 8px;
    &.done { background: #22c55e; }
    &.doing { background: #0052d9; }
    &.todo { background: #cbd5e1; }
  }
}

.ops-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
  li {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 13px;
    span { color: var(--demo-muted); }
  }
}

.chart-card { margin-bottom: 14px; }

.mobile-only { display: none; }

.continue-card {
  padding: 16px;
  border-radius: 14px;
  background: #0f172a;
  color: #fff;
  margin-bottom: 12px;
  cursor: pointer;
}
.continue-kicker { font-size: 12px; opacity: 0.75; }
.continue-title { margin-top: 4px; font-size: 18px; font-weight: 800; }
.continue-sub { margin-top: 4px; opacity: 0.8; font-size: 13px; }

.course-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border: 0;
  border-bottom: 1px solid #f0f2f5;
  background: transparent;
  cursor: pointer;
  text-align: left;
}
.course-ico {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
}
.course-body { flex: 1; }
.course-title { font-weight: 700; }
.course-sub { color: var(--demo-muted); font-size: 12px; }

@media (max-width: 960px) {
  .kpi-grid,
  .quick-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .board { grid-template-columns: 1fr; }
}

@media (max-width: 680px) {
  .top-row { flex-direction: column; align-items: stretch; }
  .search { min-width: 0; }
  .mobile-only { display: block; }
  .chart-card { display: none; }
}
</style>
