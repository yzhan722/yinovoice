<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import {
  OperatorCallRecordService,
  TenantCallRecordService,
} from '@/api/platform';
import type { NormalizedCallRecordListItem } from '@/api/platform/RealtimeVoiceService';

const props = defineProps<{
  scope: 'tenant' | 'operator';
}>();

const router = useRouter();
const recordService = props.scope === 'operator'
  ? new OperatorCallRecordService()
  : new TenantCallRecordService();
const records = ref<NormalizedCallRecordListItem[]>([]);
const loading = ref(true);
const errorMessage = ref('');
const current = ref(1);
const pageSize = 10;
const total = ref(0);
let loadGeneration = 0;

const title = computed(() => (
  props.scope === 'operator' ? '通话记录' : '网页语音 Demo 记录'
));
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

const statusLabel = (status: string) => ({
  completed: '已完成',
  interrupted: '已中断',
  failed: '失败',
}[status] || status || '—');

const statusClass = (status: string) => (
  status === 'completed' ? 'is-success' : status === 'failed' ? 'is-error' : 'is-warning'
);

const formatDateTime = (value: string) => (
  value ? value.replace('T', ' ').replace('Z', ' UTC') : '—'
);

const shortId = (value: string) => (
  value && value.length > 14 ? value.slice(0, 12) + '…' : value || '—'
);

const load = async () => {
  const generation = ++loadGeneration;
  loading.value = true;
  errorMessage.value = '';
  try {
    const response = await recordService.getList({
      current: current.value,
      page: current.value,
      pageSize,
    });
    if (generation !== loadGeneration) return;
    records.value = response?.records || response?.list || [];
    total.value = Number(response?.total || 0);
  } catch {
    if (generation !== loadGeneration) return;
    records.value = [];
    total.value = 0;
    errorMessage.value = '无法加载 Demo 通话记录，请稍后重试。';
  } finally {
    if (generation === loadGeneration) loading.value = false;
  }
};

const viewDetail = (record: NormalizedCallRecordListItem) => {
  const name = props.scope === 'operator'
    ? 'AdminCallHistoryDetail'
    : 'UserCallHistoryDetail';
  void router.push({
    name,
    params: { id: String(record.aacId || record.callId) },
  });
};

const changePage = (next: number) => {
  if (next < 1 || next > totalPages.value || next === current.value) return;
  current.value = next;
  void load();
};

onMounted(load);
</script>

<template>
  <main class="records-page">
    <header class="page-head">
      <div>
        <h1>{{ title }}</h1>
        <p>浏览器实时语音 Demo 生成的租户内记录，不是电话 CDR。</p>
      </div>
      <span class="demo-tag">Demo-only</span>
    </header>

    <aside v-if="scope === 'operator'" class="scope-notice">
      演示租户范围：当前使用配置的 Demo tenant header，仅供联调查看，不代表全局生产 RBAC。
    </aside>

    <section class="records-card">
      <div v-if="loading" class="state-box">正在加载通话记录…</div>
      <div v-else-if="errorMessage" class="state-box is-error" role="alert">
        {{ errorMessage }}
      </div>
      <div v-else-if="!records.length" class="state-box">
        暂无网页语音 Demo 记录
      </div>
      <div v-else class="records-table-wrap">
        <table class="records-table">
          <thead>
            <tr>
              <th>记录 ID</th>
              <th>客服实例</th>
              <th>方向</th>
              <th>状态</th>
              <th>开始时间</th>
              <th>时长</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in records" :key="record.aacId">
              <td><code>{{ shortId(record.callId) }}</code></td>
              <td>{{ record.assistantName || '—' }}</td>
              <td><span class="direction-tag">网页语音</span></td>
              <td>
                <span class="status-tag" :class="statusClass(record.status)">
                  {{ statusLabel(record.status) }}
                </span>
              </td>
              <td>{{ formatDateTime(record.startedAt) }}</td>
              <td>{{ record.durationSec != null ? record.durationSec + ' 秒' : '—' }}</td>
              <td>
                <button type="button" class="link-button" @click="viewDetail(record)">
                  查看详情
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <nav v-if="totalPages > 1" class="pagination" aria-label="通话记录分页">
      <button type="button" :disabled="current === 1" @click="changePage(current - 1)">
        上一页
      </button>
      <span>第 {{ current }} / {{ totalPages }} 页</span>
      <button
        type="button"
        :disabled="current === totalPages"
        @click="changePage(current + 1)"
      >
        下一页
      </button>
    </nav>
  </main>
</template>

<style scoped lang="less">
.records-page {
  display: grid;
  gap: 16px;
  max-width: 1180px;
  padding: 8px 4px 40px;
  margin: 0 auto;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

h1 {
  margin: 0;
  color: var(--td-text-color-primary, #1d2129);
  font-size: 26px;
}

.page-head p {
  margin: 7px 0 0;
  color: var(--td-text-color-secondary, #5e626b);
}

.demo-tag,
.direction-tag,
.status-tag {
  display: inline-flex;
  padding: 5px 9px;
  font-weight: 700;
  font-size: 12px;
  border-radius: 999px;
}

.demo-tag,
.direction-tag {
  color: #0052d9;
  background: #e8f1ff;
}

.scope-notice {
  padding: 12px 15px;
  color: #76520e;
  line-height: 1.6;
  background: #fff8e6;
  border: 1px solid #f3d999;
  border-radius: 9px;
}

.records-card {
  overflow: hidden;
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #e6e8eb);
  border-radius: 12px;
  box-shadow: 0 12px 34px rgb(31 66 111 / 6%);
}

.state-box {
  padding: 56px 20px;
  color: #7a8492;
  text-align: center;
}

.state-box.is-error {
  color: #a63737;
}

.records-table-wrap {
  overflow-x: auto;
}

.records-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

th,
td {
  padding: 14px 16px;
  text-align: left;
  border-bottom: 1px solid #edf0f3;
}

th {
  color: #687386;
  font-weight: 600;
  font-size: 12px;
  background: #f7f9fc;
}

td {
  color: #2d3748;
  font-size: 14px;
}

.status-tag.is-success {
  color: #176642;
  background: #e8f8f0;
}

.status-tag.is-warning {
  color: #775411;
  background: #fff5d9;
}

.status-tag.is-error {
  color: #a13a3a;
  background: #fff0f0;
}

.link-button {
  padding: 0;
  color: var(--td-brand-color, #0052d9);
  background: transparent;
  border: 0;
  cursor: pointer;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  color: #687386;
  font-size: 13px;
}

.pagination button {
  min-height: 34px;
  padding: 0 12px;
  background: #fff;
  border: 1px solid #d7dde5;
  border-radius: 7px;
}

@media (max-width: 680px) {
  .page-head {
    flex-direction: column;
  }
}
</style>
