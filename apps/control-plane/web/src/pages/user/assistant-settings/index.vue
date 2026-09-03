<template>
  <div class="instance-list">
    <div class="page-head">
      <div>
        <h1 class="title">我的实例</h1>
        <p class="sub">预置语音前台 · 可导入多行业合成演示，或点开始通话</p>
      </div>
      <div class="head-actions">
        <button
          data-testid="import-industry"
          type="button"
          class="ghost-button"
          :disabled="busyId === 'import'"
          @click="importIndustry"
        >
          导入行业演示
        </button>
        <button data-testid="new-instance" type="button" class="new-button" @click="showCreate = true">
          新建实例
        </button>
      </div>
    </div>

    <label class="show-deleted">
      <input v-model="showDeleted" type="checkbox" data-testid="show-deleted" />
      显示已删除
    </label>
    <p v-if="actionError" role="alert" class="action-error">{{ actionError }}</p>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="loadFailed" role="alert" class="state error-state">
      实例加载失败，请稍后重试。
    </div>
    <div v-else-if="list.length === 0" class="state">暂无实例</div>
    <div v-else class="list">
      <div
        v-for="item in list"
        :key="item.id"
        class="row"
        :class="{ 'is-deleted': !!item.deleted_at }"
        data-testid="instance-row"
      >
        <button
          type="button"
          class="row-main"
          :disabled="!!item.deleted_at || busyId === item.id"
          @click="goDetail(item.id)"
        >
          <div class="name-row">
            <span class="name">{{ item.display_name || '未命名实例' }}</span>
            <span v-if="item.deleted_at" class="deleted-tag">已删除</span>
            <t-tag v-else theme="success" variant="light" size="small">演示就绪</t-tag>
          </div>
          <div class="meta">{{ item.business_profile }} · v{{ item.version }}</div>
          <div v-if="item.organization_name" class="org">{{ item.organization_name }} · {{ item.primary_language }}</div>
          <div v-if="!item.deleted_at" class="score">
            <span class="gpa">8.6</span><span class="unit">/10 实例健康分</span>
          </div>
        </button>
        <div class="row-actions">
          <button
            v-if="!item.deleted_at"
            type="button"
            class="action-button primary"
            data-testid="start-voice-button"
            :disabled="busyId === item.id"
            @click="goVoice(item.id)"
          >
            开始通话
          </button>
          <button
            v-if="!item.deleted_at"
            type="button"
            class="action-button"
            data-testid="soft-delete-button"
            :disabled="busyId === item.id"
            @click="softDelete(item)"
          >
            软删除
          </button>
          <template v-else>
            <button
              type="button"
              class="action-button"
              data-testid="restore-button"
              :disabled="busyId === item.id"
              @click="restoreInstance(item)"
            >
              恢复
            </button>
            <button
              type="button"
              class="action-button danger"
              data-testid="purge-button"
              :disabled="busyId === item.id"
              @click="purgeInstance(item)"
            >
              完全删除
            </button>
          </template>
        </div>
      </div>
    </div>
    <InstanceCreateDialog v-if="showCreate" @close="showCreate = false" @created="onCreated" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { RealtimeVoiceService } from '@/api/platform';
import { storeInstanceId } from '@/api/platform/instanceSelection';
import type { CustomerServiceInstance } from '@/api/platform/RealtimeVoiceService';
import InstanceCreateDialog from './InstanceCreateDialog.vue';

const router = useRouter();
const svc = new RealtimeVoiceService();
const loading = ref(true);
const loadFailed = ref(false);
const showCreate = ref(false);
const showDeleted = ref(false);
const busyId = ref<string | null>(null);
const actionError = ref('');
const list = ref<CustomerServiceInstance[]>([]);

function goDetail(instanceId: string) {
  storeInstanceId(instanceId);
  router.push({ name: 'KnowledgeBaseIndex', query: { instanceId } });
}

function goVoice(instanceId: string) {
  storeInstanceId(instanceId);
  router.push({ name: 'UserRealtimeVoiceIndex', query: { instanceId } });
}

async function importIndustry() {
  if (busyId.value) return;
  busyId.value = 'import';
  actionError.value = '';
  try {
    await svc.importIndustryDemos();
    await loadList();
  } catch (_) {
    actionError.value = '导入行业演示失败，请稍后重试。';
  } finally {
    busyId.value = null;
  }
}

function onCreated(instance: CustomerServiceInstance) {
  showCreate.value = false;
  goDetail(instance.id);
}

async function loadList() {
  loading.value = true;
  loadFailed.value = false;
  actionError.value = '';
  try {
    const res = await svc.listCustomerServices({
      limit: 100,
      offset: 0,
      includeDeleted: showDeleted.value,
    });
    list.value = res.items;
  } catch (_) {
    list.value = [];
    loadFailed.value = true;
  } finally {
    loading.value = false;
  }
}

async function softDelete(item: CustomerServiceInstance) {
  if (item.deleted_at || busyId.value) return;
  if (!window.confirm('确认软删除该实例？可勾选“显示已删除”后恢复。')) return;
  busyId.value = item.id;
  actionError.value = '';
  try {
    await svc.deleteCustomerService(item.id);
    await loadList();
  } catch (_) {
    actionError.value = '软删除失败，请稍后重试。';
  } finally {
    busyId.value = null;
  }
}

async function restoreInstance(item: CustomerServiceInstance) {
  if (!item.deleted_at || busyId.value) return;
  busyId.value = item.id;
  actionError.value = '';
  try {
    await svc.restoreCustomerService(item.id);
    await loadList();
  } catch (_) {
    actionError.value = '恢复失败，请稍后重试。';
  } finally {
    busyId.value = null;
  }
}

async function purgeInstance(item: CustomerServiceInstance) {
  if (!item.deleted_at || busyId.value) return;
  if (!window.confirm('确认完全删除？不可恢复；若仍有通话记录将失败。')) return;
  busyId.value = item.id;
  actionError.value = '';
  try {
    await svc.purgeCustomerService(item.id);
    await loadList();
  } catch (error) {
    actionError.value = error instanceof Error
      ? error.message
      : '完全删除失败，请稍后重试。';
  } finally {
    busyId.value = null;
  }
}

watch(showDeleted, () => {
  void loadList();
});

onMounted(() => {
  void loadList();
});
</script>

<style scoped lang="less">
.instance-list {
  padding: 8px 4px 40px;
  max-width: 720px;
  margin: 0 auto;
  font-family: var(--demo-font);
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.head-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.show-deleted {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--demo-muted);
}

.action-error {
  margin: 0 0 12px;
  color: #c62828;
  font-size: 13px;
}

.new-button {
  flex-shrink: 0;
  padding: 9px 16px;
  border: 0;
  border-radius: 7px;
  background: var(--demo-primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.ghost-button {
  flex-shrink: 0;
  padding: 9px 16px;
  border: 1px solid var(--demo-line);
  border-radius: 7px;
  background: #fff;
  color: var(--demo-ink);
  font-weight: 700;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: default;
  }
}

.error-state { color: #c62828; }

.title {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  color: var(--demo-ink);
}

.sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--demo-muted);
}

.state {
  color: var(--demo-muted);
  padding: 24px 0;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  padding: 18px 20px;
  border: 1px solid var(--demo-line);
  border-radius: var(--demo-radius);
  background: var(--demo-card);
  box-shadow: var(--demo-shadow);
}

.row.is-deleted {
  opacity: 0.78;
}

.row-main {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  padding: 0;
  text-align: left;
  cursor: pointer;

  &:disabled {
    cursor: default;
  }
}

.row-actions {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  gap: 8px;
}

.action-button {
  padding: 7px 12px;
  border: 1px solid var(--demo-line);
  border-radius: 6px;
  background: #fff;
  color: var(--demo-ink);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: default;
  }

  &.primary {
    border-color: var(--demo-primary);
    background: var(--demo-primary);
    color: #fff;
  }

  &.danger {
    border-color: #c62828;
    color: #c62828;
  }
}

.deleted-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eceff1;
  color: #546e7a;
  font-size: 12px;
  font-weight: 700;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.name {
  font-size: 16px;
  font-weight: 700;
  color: var(--demo-ink);
}

.meta {
  margin-top: 6px;
  font-size: 13px;
  color: var(--demo-muted);
}

.org {
  margin-top: 4px;
  font-size: 12px;
  color: var(--demo-muted);
}

.score {
  margin-top: 10px;
  display: flex;
  align-items: baseline;
  gap: 6px;
  .gpa {
    font-size: 28px;
    font-weight: 800;
    color: var(--demo-primary);
  }
  .unit {
    font-size: 12px;
    color: var(--demo-muted);
    font-weight: 700;
  }
}

@media (max-width: 768px) {
  .instance-list {
    padding: 12px 4px 28px;
    max-width: 100%;
  }

  .title {
    font-size: 20px;
  }

  .row {
    padding: 14px 14px;
    flex-direction: column;
    align-items: flex-start;
  }

  .row-actions {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
