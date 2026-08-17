<template>
  <div class="instance-list">
    <div class="page-head">
      <div>
        <h1 class="title">我的实例</h1>
        <p class="sub">预置语音前台 · 查看机构配置与通话接入位</p>
      </div>
      <button data-testid="new-instance" type="button" class="new-button" @click="showCreate = true">
        新建实例
      </button>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="loadFailed" role="alert" class="state error-state">
      实例加载失败，请稍后重试。
    </div>
    <div v-else-if="list.length === 0" class="state">暂无实例</div>
    <div v-else class="list">
      <button
        v-for="item in list"
        :key="item.id"
        type="button"
        class="row"
        @click="goDetail(item.id)"
      >
        <div class="row-main">
          <div class="name-row">
            <span class="name">{{ item.display_name || '未命名实例' }}</span>
            <t-tag theme="success" variant="light" size="small">演示就绪</t-tag>
          </div>
          <div class="meta">{{ item.business_profile }} · v{{ item.version }}</div>
          <div v-if="item.organization_name" class="org">{{ item.organization_name }} · {{ item.primary_language }}</div>
          <div class="score"><span class="gpa">8.6</span><span class="unit">/10 实例健康分</span></div>
        </div>
        <span class="arrow">查看详情</span>
      </button>
    </div>
    <InstanceCreateDialog v-if="showCreate" @close="showCreate = false" @created="onCreated" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
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
const list = ref<CustomerServiceInstance[]>([]);

function goDetail(instanceId: string) {
  storeInstanceId(instanceId);
  router.push({ name: 'KnowledgeBaseIndex', query: { instanceId } });
}

function onCreated(instance: CustomerServiceInstance) {
  showCreate.value = false;
  goDetail(instance.id);
}

onMounted(async () => {
  try {
    const res = await svc.listCustomerServices({ limit: 100, offset: 0 });
    list.value = res.items;
  } catch (_) {
    list.value = [];
    loadFailed.value = true;
  } finally {
    loading.value = false;
  }
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
  margin-bottom: 18px;
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
  cursor: pointer;
  text-align: left;

  &:hover {
    border-color: var(--demo-primary);
  }
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

.arrow {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--demo-primary);
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

  .arrow {
    margin-top: 8px;
  }
}
</style>
