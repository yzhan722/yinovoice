<template>
  <div class="instance-list">
    <div class="page-head">
      <div>
        <h1 class="title">我的实例</h1>
        <p class="sub">预置语音前台 · 查看机构配置与通话接入位</p>
      </div>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="list.length === 0" class="state">暂无实例</div>
    <div v-else class="list">
      <button
        v-for="item in list"
        :key="item.attId"
        type="button"
        class="row"
        @click="goDetail(item.attId)"
      >
        <div class="row-main">
          <div class="name-row">
            <span class="name">{{ item.attName || '未命名实例' }}</span>
            <t-tag theme="success" variant="light" size="small">演示就绪</t-tag>
          </div>
          <div class="meta">{{ item.templateName || item.templateId }} · v{{ item.templateVersion }}</div>
          <div v-if="item.orgName" class="org">{{ item.orgName }} · {{ item.businessHours || '营业时间见详情' }}</div>
          <div class="score"><span class="gpa">8.6</span><span class="unit">/10 实例健康分</span></div>
        </div>
        <span class="arrow">查看详情</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { TenantInstanceService } from '@/api/platform';

const router = useRouter();
const svc = new TenantInstanceService();
const loading = ref(true);
const list = ref<any[]>([]);

function goDetail(attId: number) {
  router.push({ name: 'UserAssistantDetail', params: { attId: String(attId) } });
}

onMounted(async () => {
  try {
    const res: any = await svc.getMyList();
    list.value = Array.isArray(res) ? res : res?.list ?? [];
  } catch (_) {
    list.value = [];
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
  margin-bottom: 18px;
}

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
