<template>
  <div class="create-instance-page">
    <t-card title="从模板创建 Voice Agent 实例">
      <t-steps :current="step" style="margin-bottom: 24px">
        <t-step-item title="选择模板" />
        <t-step-item title="填写机构字段" />
        <t-step-item title="确认创建" />
      </t-steps>

      <!-- Step 0 -->
      <div v-show="step === 0">
        <t-radio-group v-model="selectedId" class="tpl-group">
          <t-radio
            v-for="tpl in templates"
            :key="tpl.id"
            :value="tpl.id"
            class="tpl-radio"
          >
            <div class="tpl-card">
              <div class="tpl-title">
                {{ tpl.name }}
                <t-tag size="small" variant="light">{{ tpl.version }}</t-tag>
                <t-tag size="small" theme="primary" variant="light">{{ tpl.type }}</t-tag>
              </div>
              <div class="tpl-desc">{{ tpl.description }}</div>
            </div>
          </t-radio>
        </t-radio-group>
        <t-empty v-if="!loading && templates.length === 0" description="暂无已发布模板，请联系平台运营发布。" />
        <div class="actions">
          <t-button theme="primary" :disabled="!selectedId" @click="goFill">下一步</t-button>
        </div>
      </div>

      <!-- Step 1 -->
      <div v-show="step === 1">
        <t-form ref="formRef" :data="form" label-width="140px" @submit="onFillSubmit">
          <t-form-item label="实例显示名" name="attName" :rules="[{ required: true, message: '请填写实例名' }]">
            <t-input v-model="form.attName" placeholder="例如：太平洋口腔 · 新北前台" />
          </t-form-item>
          <t-form-item
            v-for="f in selectedTemplate?.requiredFields || []"
            :key="f.key"
            :label="f.label"
            :name="f.key"
            :rules="f.required ? [{ required: true, message: `请填写${f.label}` }] : []"
          >
            <t-input v-model="form.fields[f.key]" :placeholder="f.label" />
          </t-form-item>
          <t-form-item>
            <t-space>
              <t-button variant="outline" @click="step = 0">上一步</t-button>
              <t-button theme="primary" type="submit">下一步</t-button>
            </t-space>
          </t-form-item>
        </t-form>
      </div>

      <!-- Step 2 -->
      <div v-show="step === 2">
        <t-descriptions title="将创建的实例" :column="1" bordered>
          <t-descriptions-item label="模板">{{ selectedTemplate?.name }} @ {{ selectedTemplate?.version }}</t-descriptions-item>
          <t-descriptions-item label="实例名">{{ form.attName }}</t-descriptions-item>
          <t-descriptions-item
            v-for="f in selectedTemplate?.requiredFields || []"
            :key="f.key"
            :label="f.label"
          >{{ form.fields[f.key] || '—' }}</t-descriptions-item>
        </t-descriptions>
        <t-alert
          theme="info"
          message="创建会绑定该模板版本快照；后续模板升级需显式操作，不会自动覆盖本实例。"
          style="margin-top: 16px"
        />
        <div class="actions">
          <t-space>
            <t-button variant="outline" @click="step = 1">上一步</t-button>
            <t-button theme="primary" :loading="creating" @click="onCreate">确认创建</t-button>
          </t-space>
        </div>
      </div>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { TenantInstanceFactoryService } from '@/api/platform';

const router = useRouter();
const factory = new TenantInstanceFactoryService();

const loading = ref(false);
const creating = ref(false);
const step = ref(0);
const templates = ref<any[]>([]);
const selectedId = ref('');
const formRef = ref();
const form = reactive({
  attName: '',
  fields: {} as Record<string, string>,
});

const selectedTemplate = computed(() => templates.value.find((t) => t.id === selectedId.value));

async function load() {
  loading.value = true;
  try {
    const res: any = await factory.listPublishedTemplates();
    templates.value = res?.list ?? [];
    if (templates.value.length && !selectedId.value) {
      selectedId.value = templates.value[0].id;
    }
  } catch (e: any) {
    MessagePlugin.error(e?.message || '加载模板失败');
  } finally {
    loading.value = false;
  }
}

function goFill() {
  if (!selectedTemplate.value) return;
  form.fields = {};
  for (const f of selectedTemplate.value.requiredFields || []) {
    form.fields[f.key] = '';
  }
  if (!form.attName && form.fields.orgName) form.attName = form.fields.orgName;
  step.value = 1;
}

async function onFillSubmit({ validateResult }: any) {
  if (validateResult !== true) return;
  if (!form.attName.trim()) {
    form.attName = form.fields.orgName || '';
  }
  step.value = 2;
}

async function onCreate() {
  creating.value = true;
  try {
    const inst: any = await factory.createFromTemplate({
      templateId: selectedId.value,
      attName: form.attName,
      fields: { ...form.fields },
    });
    MessagePlugin.success('实例已创建');
    router.push({ name: 'UserAssistantDetail', params: { attId: String(inst.attId) } });
  } catch (e: any) {
    MessagePlugin.error(e?.message || '创建失败');
  } finally {
    creating.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="less">
.create-instance-page {
  padding: 16px;
  .tpl-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
  }
  .tpl-radio {
    width: 100%;
    margin-right: 0;
    border: 1px solid var(--td-component-border);
    border-radius: 6px;
    padding: 12px;
  }
  .tpl-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }
  .tpl-desc {
    margin-top: 6px;
    color: var(--td-text-color-secondary);
    font-size: 13px;
  }
  .actions {
    margin-top: 24px;
  }
}
</style>
