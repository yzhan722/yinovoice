<template>
  <div class="templates-page">
    <t-card title="Agent 模板">
      <template #actions>
        <t-space>
          <t-button variant="outline" @click="load">刷新</t-button>
        </t-space>
      </template>

      <t-table
        row-key="id"
        :data="list"
        :columns="columns"
        :loading="loading"
        :pagination="{ pageSize: 10, total: list.length }"
      >
        <template #status="{ row }">
          <t-tag :theme="statusTheme(row.status)" variant="light">{{ statusLabel(row.status) }}</t-tag>
        </template>
        <template #type="{ row }">
          {{ row.type === 'domain' ? 'Domain' : 'Generic' }}
        </template>
        <template #parent="{ row }">
          <span v-if="row.parentTemplateId">{{ row.parentTemplateId }} @ {{ row.parentVersion }}</span>
          <span v-else class="muted">—</span>
        </template>
        <template #op="{ row }">
          <t-space>
            <t-button
              v-if="row.status === 'draft'"
              size="small"
              theme="primary"
              @click="onPublish(row)"
            >发布</t-button>
            <t-button
              v-if="row.status === 'published'"
              size="small"
              theme="warning"
              variant="outline"
              @click="onDisable(row)"
            >停用</t-button>
            <t-button
              v-if="row.status === 'disabled'"
              size="small"
              theme="primary"
              variant="outline"
              @click="onPublish(row)"
            >重新发布</t-button>
            <t-button size="small" variant="text" @click="showDetail(row)">详情</t-button>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <t-drawer v-model:visible="detailVisible" size="480px" :header="detail?.name || '模板详情'">
      <template v-if="detail">
        <t-descriptions :column="1" bordered>
          <t-descriptions-item label="ID">{{ detail.id }}</t-descriptions-item>
          <t-descriptions-item label="版本">{{ detail.version }}</t-descriptions-item>
          <t-descriptions-item label="状态">{{ statusLabel(detail.status) }}</t-descriptions-item>
          <t-descriptions-item label="类型">{{ detail.type }}</t-descriptions-item>
          <t-descriptions-item label="说明">{{ detail.description }}</t-descriptions-item>
          <t-descriptions-item label="发布时间">{{ detail.publishedAt || '—' }}</t-descriptions-item>
        </t-descriptions>
        <h4 style="margin-top: 16px">创建实例必填字段</h4>
        <t-list :split="true">
          <t-list-item v-for="f in detail.requiredFields || []" :key="f.key">
            {{ f.label }}
            <template #action>
              <t-tag v-if="f.required" size="small" theme="danger" variant="light">必填</t-tag>
              <t-tag v-else size="small" variant="light">可选</t-tag>
            </template>
          </t-list-item>
        </t-list>
      </template>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next';
import { OperatorTemplateService } from '@/api/platform';

const svc = new OperatorTemplateService();
const loading = ref(false);
const list = ref<any[]>([]);
const detailVisible = ref(false);
const detail = ref<any>(null);

const columns = [
  { colKey: 'name', title: '名称', width: 180 },
  { colKey: 'version', title: '版本', width: 120 },
  { colKey: 'type', title: '类型', width: 100 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'parent', title: '父模板', ellipsis: true },
  { colKey: 'description', title: '说明', ellipsis: true },
  { colKey: 'op', title: '操作', width: 220, fixed: 'right' },
];

function statusLabel(s: string) {
  return ({ draft: '草稿', published: '已发布', disabled: '已停用' } as any)[s] || s;
}
function statusTheme(s: string) {
  return ({ draft: 'warning', published: 'success', disabled: 'default' } as any)[s] || 'default';
}

async function load() {
  loading.value = true;
  try {
    const res: any = await svc.list();
    list.value = res?.list ?? [];
  } catch (e: any) {
    MessagePlugin.error(e?.message || '加载失败');
    list.value = [];
  } finally {
    loading.value = false;
  }
}

function showDetail(row: any) {
  detail.value = row;
  detailVisible.value = true;
}

async function onPublish(row: any) {
  const dlg = DialogPlugin.confirm({
    header: '发布模板',
    body: `确认发布「${row.name}」${row.version}？发布后租户可据此创建实例；内容快照不可原地修改。`,
    onConfirm: async () => {
      try {
        await svc.publish(row.id);
        MessagePlugin.success('已发布');
        dlg.hide();
        await load();
      } catch (e: any) {
        MessagePlugin.error(e?.message || '发布失败');
      }
    },
  });
}

async function onDisable(row: any) {
  const dlg = DialogPlugin.confirm({
    header: '停用模板',
    body: `停用后将阻止新建实例，不影响已绑定该版本的现有实例。确认停用「${row.name}」？`,
    onConfirm: async () => {
      try {
        await svc.disable(row.id);
        MessagePlugin.success('已停用');
        dlg.hide();
        await load();
      } catch (e: any) {
        MessagePlugin.error(e?.message || '停用失败');
      }
    },
  });
}

onMounted(load);
</script>

<style scoped lang="less">
.templates-page {
  padding: 16px;
  .muted {
    color: var(--td-text-color-placeholder);
  }
}
</style>
