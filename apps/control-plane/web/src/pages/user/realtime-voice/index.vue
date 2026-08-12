<script setup lang="ts">
import { DEMO_CUSTOMER_SERVICE_ID } from '@/api/platform/RealtimeVoiceService';
import LiveKitRealtimePanel from '@/components/realtime-voice/LiveKitRealtimePanel.vue';
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

    <LiveKitRealtimePanel :customer-service-id="DEMO_CUSTOMER_SERVICE_ID" />
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
