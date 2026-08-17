<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { RealtimeVoiceService } from '@/api/platform/RealtimeVoiceService';
import {
  loadStoredInstanceId,
  resolveInstanceSelection,
  storeInstanceId,
} from '@/api/platform/instanceSelection';
import LiveKitRealtimePanel from '@/components/realtime-voice/LiveKitRealtimePanel.vue';

const route = useRoute();
const service = new RealtimeVoiceService();
const customerServiceId = ref<string | null>(null);
const loading = ref(true);
const loadFailed = ref(false);

async function loadInstances() {
  loading.value = true;
  loadFailed.value = false;
  try {
    const page = await service.listCustomerServices({ limit: 100, offset: 0 });
    customerServiceId.value = resolveInstanceSelection({
      availableIds: page.items.map((item) => item.id),
      routeId: typeof route.query.instanceId === 'string' ? route.query.instanceId : null,
      storedId: loadStoredInstanceId(),
    });
    storeInstanceId(customerServiceId.value);
  } catch {
    customerServiceId.value = null;
    loadFailed.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(loadInstances);
</script>

<template>
  <main class="realtime-page">
    <header class="page-head">
      <div>
        <h1>实时语音</h1>
        <p>浏览器麦克风连续对话与实时字幕演示</p>
      </div>
      <span class="demo-tag">本地 Demo</span>
    </header>

    <div class="demo-boundary" role="note">
      本地网页实时语音 Demo；电话、预约、知识库尚未接通。
    </div>

    <div v-if="loading" class="demo-boundary">正在加载语音实例…</div>
    <div v-else-if="loadFailed" class="demo-boundary">实例加载失败，请稍后重试。</div>
    <div v-else-if="!customerServiceId" class="demo-boundary">当前租户暂无可用语音实例。</div>
    <LiveKitRealtimePanel v-else :customer-service-id="customerServiceId" />
  </main>
</template>

<style scoped lang="less">
.realtime-page {
  display: grid;
  gap: 18px;
  max-width: 1120px;
  padding: 8px 4px 40px;
  margin: 0 auto;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-head h1 {
  margin: 0;
  color: var(--td-text-color-primary);
  font-size: 26px;
}

.page-head p {
  margin: 7px 0 0;
  color: var(--td-text-color-secondary);
}

.demo-tag {
  flex: 0 0 auto;
  padding: 6px 10px;
  color: #0052d9;
  font-weight: 700;
  font-size: 12px;
  background: #e8f1ff;
  border-radius: 999px;
}

.demo-boundary {
  padding: 12px 15px;
  color: #76520e;
  line-height: 1.6;
  background: #fff8e6;
  border: 1px solid #f3d999;
  border-radius: 9px;
}

@media (max-width: 680px) {
  .realtime-page {
    padding: 4px 0 28px;
  }

  .page-head {
    flex-direction: column;
  }
}
</style>
