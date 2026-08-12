<template>
  <div class="user-assistant-detail">
    <t-card :title="t('pages.aiVoice.userCenter.assistantSettings.title')">
      <template #actions>
        <t-button theme="default" @click="handleBack">
          {{ t('pages.aiVoice.userCenter.assistantSettings.back') }}
        </t-button>
      </template>

      <div v-if="loading" class="loading-container">
        <t-loading />
      </div>

      <div v-else-if="assistantData" class="detail-content">
        <t-tabs v-model="activeTab">
          <t-tab-panel value="overview" label="实例概览">
            <div class="settings-content overview-panel">
              <t-descriptions :column="2" bordered>
                <t-descriptions-item label="实例名称">{{ assistantData.attName || '—' }}</t-descriptions-item>
                <t-descriptions-item label="实例 ID">{{ assistantData.attId }}</t-descriptions-item>
                <t-descriptions-item label="绑定模板">{{ assistantData.templateName || '—' }}</t-descriptions-item>
                <t-descriptions-item label="模板版本">{{ assistantData.templateVersion || '—' }}</t-descriptions-item>
              </t-descriptions>

              <h4 class="section-title">机构信息</h4>
              <t-descriptions v-if="fieldEntries.length" :column="1" bordered>
                <t-descriptions-item v-for="item in fieldEntries" :key="item.key" :label="item.label">
                  {{ item.value || '—' }}
                </t-descriptions-item>
              </t-descriptions>
              <t-empty v-else description="暂无机构字段" />

              <h4 class="section-title">通话能力（路径 A 接入位）</h4>
              <t-descriptions :column="1" bordered>
                <t-descriptions-item label="线路 / SIP">待通话系统接入</t-descriptions-item>
                <t-descriptions-item label="通话记录">
                  由 TenantCallRecordService 按实例过滤（attId={{ assistantData.attId }}）
                </t-descriptions-item>
                <t-descriptions-item label="开关">VITE_CALL_SYSTEM_READY</t-descriptions-item>
              </t-descriptions>
            </div>
          </t-tab-panel>

          <t-tab-panel value="advanced" label="高级配置（可选）">
            <div class="settings-content">
              <t-collapse v-model="advancedPanels">
                <t-collapse-panel value="model" :header="t('pages.aiVoice.userCenter.assistantSettings.modelConfig')">
                  <t-form :data="modelFormData" label-width="200px" @submit="handleModelSubmit">
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.assistantName')">
                      <t-input :model-value="assistantData?.attName" disabled />
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.systemPrompt')">
                      <t-textarea
                        v-model="modelFormData.systemMessage"
                        :autosize="{ minRows: 8, maxRows: 16 }"
                        :placeholder="t('pages.aiVoice.admin.assistantList.systemPromptPlaceholder')"
                      />
                    </t-form-item>
                    <t-form-item>
                      <t-space>
                        <t-button theme="primary" type="submit">{{ t('pages.aiVoice.userCenter.assistantSettings.save') }}</t-button>
                        <t-button theme="default" @click="handleModelReset">{{ t('pages.aiVoice.admin.assistantList.reset') }}</t-button>
                      </t-space>
                    </t-form-item>
                  </t-form>
                </t-collapse-panel>

                <t-collapse-panel value="voice" :header="t('pages.aiVoice.userCenter.assistantSettings.voiceConfig')">
                  <t-form :data="voiceFormData" label-width="200px" @submit="handleVoiceSubmit">
                    <t-form-item :label="t('pages.aiVoice.userCenter.assistantSettings.voice')">
                      <t-select
                        v-model="voiceFormData.voiceId"
                        :options="voiceOptions"
                        :placeholder="t('pages.aiVoice.admin.assistantList.pleaseSelect')"
                      />
                    </t-form-item>
                    <t-form-item>
                      <t-space>
                        <t-button theme="primary" type="submit">{{ t('pages.aiVoice.userCenter.assistantSettings.save') }}</t-button>
                        <t-button theme="default" @click="handleVoiceReset">{{ t('pages.aiVoice.admin.assistantList.reset') }}</t-button>
                      </t-space>
                    </t-form-item>
                  </t-form>
                </t-collapse-panel>

                <t-collapse-panel value="messages" :header="t('pages.aiVoice.userCenter.assistantSettings.messageConfig')">
                  <t-form :data="messageFormData" label-width="200px" @submit="handleMessageSubmit">
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.firstMessage')">
                      <t-textarea v-model="messageFormData.firstMessage" :autosize="{ minRows: 3, maxRows: 6 }" />
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.voicemailMessage')">
                      <t-textarea v-model="messageFormData.voicemailMessage" :autosize="{ minRows: 3, maxRows: 6 }" />
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.endCallMessage')">
                      <t-textarea v-model="messageFormData.endCallMessage" :autosize="{ minRows: 3, maxRows: 6 }" />
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.forwardingPhone')">
                      <t-input v-model="messageFormData.forwardingPhone" />
                    </t-form-item>
                    <t-form-item>
                      <t-space>
                        <t-button theme="primary" type="submit">{{ t('pages.aiVoice.userCenter.assistantSettings.save') }}</t-button>
                        <t-button theme="default" @click="handleMessageReset">{{ t('pages.aiVoice.admin.assistantList.reset') }}</t-button>
                      </t-space>
                    </t-form-item>
                  </t-form>
                </t-collapse-panel>
              </t-collapse>
            </div>
          </t-tab-panel>
        </t-tabs>
      </div>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { MessagePlugin } from 'tdesign-vue-next';
import { ref, reactive, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { TenantInstanceService as UserAssistantService } from '@/api/platform';
import { UserDictionaryService } from '@/api/UserDictionaryService';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const userAssistantService = new UserAssistantService();
const userDictionaryService = new UserDictionaryService();

const attId = computed(() => Number(route.params.attId));
const loading = ref(false);
const assistantData = ref<any>(null);
const activeTab = ref('overview');
const advancedPanels = ref<string[]>([]);
const fieldLabelMap: Record<string, string> = {
  orgName: '机构名称',
  address: '地址',
  businessHours: '营业时间',
  contactPhone: '联系电话',
  doctors: '医生名单',
  services: '主要服务',
  notifyStaff: '人工通知对象',
};
const fieldEntries = computed(() => {
  const fields = assistantData.value?.fields;
  if (!fields || typeof fields !== 'object') return [];
  return Object.keys(fields).map((key) => ({
    key,
    label: fieldLabelMap[key] || key,
    value: fields[key],
  }));
});

const voiceFormData = reactive({
  provider: '',
  voiceId: '',
  model: '',
  stability: 0.5,
  similarityBoost: 0.75,
});

const modelFormData = reactive({
  provider: '',
  model: '',
  temperature: 0.7,
  maxTokens: 2000,
  systemMessage: '',
  toolIds: [] as string[],
});

const transcriberFormData = reactive({
  provider: '',
  model: '',
  language: 'en',
});

const messageFormData = reactive({
  firstMessage: '',
  voicemailMessage: '',
  endCallMessage: '',
  forwardingPhone: '',
});

const modelProviderOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Google', value: 'google' },
  { label: 'DeepSeek', value: 'deepseek' },
];

const modelOptionsMap: Record<string, { label: string; value: string }[]> = {
  openai: [
    { label: 'gpt-4o', value: 'gpt-4o' },
    { label: 'gpt-4o-mini', value: 'gpt-4o-mini' },
    { label: 'gpt-5', value: 'gpt-5' },
    { label: 'gpt-5.1', value: 'gpt-5.1' },
    { label: 'gpt-5.2', value: 'gpt-5.2' },
  ],
  google: [
    { label: 'gemini-2.5-pro', value: 'gemini-2.5-pro' },
    { label: 'gemini-2.5-flash', value: 'gemini-2.5-flash' },
  ],
  deepseek: [
    { label: 'deepseek-chat', value: 'deepseek-chat' },
    { label: 'deepseek-reasoner', value: 'deepseek-reasoner' },
  ],
};

const voiceProviderOptions = [
  { label: 'Built-in', value: 'vapi' },
  { label: '11Labs', value: '11labs' },
];

const voiceOptionsMap: Record<string, { label: string; value: string }[]> = {
  vapi: [
    { label: 'Elliot', value: 'elliot' },
    { label: 'Kylie', value: 'kylie' },
    { label: 'Rohan', value: 'rohan' },
    { label: 'Lily', value: 'lily' },
    { label: 'Savannah', value: 'savannah' },
    { label: 'Hana', value: 'hana' },
    { label: 'Neha', value: 'neha' },
    { label: 'Cole', value: 'cole' },
    { label: 'Harry', value: 'harry' },
    { label: 'Paige', value: 'paige' },
    { label: 'Spencer', value: 'spencer' },
    { label: 'Leah', value: 'leah' },
    { label: 'Tara', value: 'tara' },
    { label: 'Jess', value: 'jess' },
    { label: 'Leo', value: 'leo' },
    { label: 'Dan', value: 'dan' },
    { label: 'Mia', value: 'mia' },
    { label: 'Zac', value: 'zac' },
    { label: 'Zoe', value: 'zoe' },
  ],
  '11labs': [
    { label: 'Burt', value: 'burt' },
    { label: 'Marissa', value: 'marissa' },
    { label: 'Andrea', value: 'andrea' },
    { label: 'Sarah', value: 'sarah' },
    { label: 'Phillip', value: 'phillip' },
    { label: 'Steve', value: 'steve' },
    { label: 'Joseph', value: 'joseph' },
    { label: 'Myra', value: 'myra' },
    { label: 'Paula', value: 'paula' },
    { label: 'Ryan', value: 'ryan' },
    { label: 'Drew', value: 'drew' },
    { label: 'Paul', value: 'paul' },
    { label: 'MRB', value: 'mrb' },
    { label: 'Matilda', value: 'matilda' },
    { label: 'Mark', value: 'mark' },
  ],
};

const elevenLabsModelOptions: { label: string; value: string; description?: string }[] = [
  { label: 'Eleven Multilingual v2', value: 'eleven_multilingual_v2', description: 'Our state of the art multilingual speech synthesis model, able to generate life-like speech in 29 languages.' },
  { label: 'Eleven Turbo v2', value: 'eleven_turbo_v2', description: 'Our cutting-edge turbo model is ideally suited for tasks demanding extremely low latency.' },
  { label: 'Eleven Turbo v2.5', value: 'eleven_turbo_v2_5', description: 'Our cutting-edge turbo model is ideally suited for tasks demanding extremely low latency.' },
  { label: 'Eleven Flash v2', value: 'eleven_flash_v2', description: 'Our newest model, Flash, generates speech in ~75ms (excluding network/application latency).' },
  { label: 'Eleven Flash v2.5', value: 'eleven_flash_v2_5', description: 'Our newest model, Flash, generates speech in ~75ms (excluding network/application latency).' },
  { label: 'Eleven English v1', value: 'eleven_monolingual_v1', description: 'Use our standard English language model to generate speech in a variety of voices, styles and moods.' },
];

const transcriberProviderOptions = [
  { label: 'Deepgram', value: 'deepgram' },
  { label: 'Assembly AI', value: 'assembly-ai' },
];

const languageOptions = [
  { label: 'English', value: 'en' },
  { label: 'Chinese', value: 'zh' },
  { label: 'Spanish', value: 'es' },
  { label: 'French', value: 'fr' },
  { label: 'German', value: 'de' },
];

const modelOptions = computed(() => modelOptionsMap[modelFormData.provider] || []);
// 从字典表获取 Voice 选项
const voiceOptions = ref<{ label: string; value: string }[]>([]);

async function loadVoiceOptions() {
  try {
    const res: any = await userDictionaryService.getVoices();
    voiceOptions.value = (res || []).map((item: any) => ({
      label: item.diyName,
      value: item.diyCode,
    }));
  } catch (e) {
    console.error(e);
    MessagePlugin.error('加载 Voice 列表失败');
  }
}

function parseConfigurations(data: any) {
  try {
    if (data.attVoiceConfig) {
      const voiceData = JSON.parse(data.attVoiceConfig);
      voiceFormData.provider = voiceData.provider || '';
      voiceFormData.voiceId = voiceData.voiceId || '';
      voiceFormData.model = voiceData.model || '';
      voiceFormData.stability = voiceData.stability || 0.5;
      voiceFormData.similarityBoost = voiceData.similarityBoost || 0.75;
    }
    if (data.attModelConfig) {
      const modelData = JSON.parse(data.attModelConfig);
      modelFormData.provider = modelData.provider || '';
      modelFormData.model = modelData.model || '';
      modelFormData.temperature = modelData.temperature || 0.7;
      modelFormData.maxTokens = modelData.maxTokens || 2000;
      modelFormData.toolIds = modelData.toolIds || [];
    }
    
    // 从后端返回的分离字段填充用户 System Prompt（用户只能看到自己的部分）
    modelFormData.systemMessage = data.userSystemPrompt || '';
    if (data.attTranscriberConfig) {
      const transcriberData = JSON.parse(data.attTranscriberConfig);
      transcriberFormData.provider = transcriberData.provider || '';
      transcriberFormData.model = transcriberData.model || '';
      transcriberFormData.language = transcriberData.language || 'en';
    }
    messageFormData.firstMessage = data.attFirstMessage || '';
    messageFormData.voicemailMessage = data.attVoicemailMessage || '';
    messageFormData.endCallMessage = data.attEndCallMessage || '';
    messageFormData.forwardingPhone = data.attForwardingPhone || '';
  } catch (e) {
    console.warn('Parse config failed', e);
  }
}

async function updateAssistant(params: any) {
  await userAssistantService.update({ ...params, attId: attId.value });
  await loadDetail();
}

const handleBack = () => {
  router.push({ name: 'AssistantSettingsIndex' });
};

const loadDetail = async () => {
  loading.value = true;
  try {
    const res: any = await userAssistantService.getDetail(attId.value);
    assistantData.value = res;
    parseConfigurations(res);
  } catch (_) {
    MessagePlugin.error(t('pages.aiVoice.userCenter.assistantSettings.loadDetailFailed'));
  } finally {
    loading.value = false;
  }
};

const handleVoiceSubmit = async () => {
  try {
    // 固定 provider 为 11labs
    const voiceConfig: any = {
      provider: '11labs',
      voiceId: voiceFormData.voiceId,
      stability: voiceFormData.stability,
      similarityBoost: voiceFormData.similarityBoost,
    };
    if (voiceFormData.model) voiceConfig.model = voiceFormData.model;
    await updateAssistant({ attVoiceConfig: JSON.stringify(voiceConfig) });
    MessagePlugin.success(t('pages.aiVoice.userCenter.assistantSettings.saveSuccess'));
  } catch (_) {
    MessagePlugin.error(t('pages.aiVoice.userCenter.assistantSettings.saveFailed'));
  }
};

const handleModelSubmit = async () => {
  try {
    // 用户端只传递 userSystemPrompt，后端会自动合并
    await updateAssistant({ 
      userSystemPrompt: modelFormData.systemMessage 
    });
    MessagePlugin.success(t('pages.aiVoice.userCenter.assistantSettings.saveSuccess'));
  } catch (_) {
    MessagePlugin.error(t('pages.aiVoice.userCenter.assistantSettings.saveFailed'));
  }
};


const handleMessageSubmit = async () => {
  try {
    await updateAssistant({
      attFirstMessage: messageFormData.firstMessage,
      attVoicemailMessage: messageFormData.voicemailMessage,
      attEndCallMessage: messageFormData.endCallMessage,
      attForwardingPhone: messageFormData.forwardingPhone,
    });
    MessagePlugin.success(t('pages.aiVoice.userCenter.assistantSettings.saveSuccess'));
  } catch (_) {
    MessagePlugin.error(t('pages.aiVoice.userCenter.assistantSettings.saveFailed'));
  }
};


const handleModelReset = () => {
  if (assistantData.value) {
    try {
      if (assistantData.value.attModelConfig) {
        const modelData = JSON.parse(assistantData.value.attModelConfig);
        modelFormData.provider = modelData.provider || '';
        modelFormData.model = modelData.model || '';
        modelFormData.temperature = modelData.temperature || 0.7;
        modelFormData.maxTokens = modelData.maxTokens || 2000;
        modelFormData.toolIds = modelData.toolIds || [];
      }
      
      // 从后端返回的分离字段重置用户 System Prompt
      modelFormData.systemMessage = assistantData.value.userSystemPrompt || '';
    } catch (_) {}
  }
};

const handleVoiceReset = () => {
  if (assistantData.value?.attVoiceConfig) {
    try {
      const voiceData = JSON.parse(assistantData.value.attVoiceConfig);
      voiceFormData.provider = voiceData.provider || '';
      voiceFormData.voiceId = voiceData.voiceId || '';
      voiceFormData.model = voiceData.model || '';
      voiceFormData.stability = voiceData.stability || 0.5;
      voiceFormData.similarityBoost = voiceData.similarityBoost || 0.75;
    } catch (_) {}
  }
};


const handleMessageReset = () => {
  if (assistantData.value) {
    messageFormData.firstMessage = assistantData.value.attFirstMessage || '';
    messageFormData.voicemailMessage = assistantData.value.attVoicemailMessage || '';
    messageFormData.endCallMessage = assistantData.value.attEndCallMessage || '';
    messageFormData.forwardingPhone = assistantData.value.attForwardingPhone || '';
  }
};

onMounted(() => {
  loadDetail();
  loadVoiceOptions();
});
</script>

<style scoped lang="less">
.user-assistant-detail {
  padding: 24px;

  .loading-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 200px;
  }

  .detail-content .settings-content {
    padding: 24px 0;

    &.overview-panel .section-title {
      margin: 24px 0 12px;
      font-size: 14px;
      font-weight: 600;
      color: var(--td-text-color-primary);
    }

    .slider-value {
      text-align: center;
      margin-top: 8px;
      font-weight: 600;
      color: var(--td-text-color-primary);
    }

    .model-name {
      font-weight: 500;
      color: var(--td-text-color-primary);
      margin-bottom: 4px;
    }

    .model-description {
      font-size: 12px;
      color: var(--td-text-color-placeholder);
      line-height: 1.4;
    }
  }
}

@media (max-width: 768px) {
  .user-assistant-detail {
    padding: 12px 4px 28px;

    .detail-content .settings-content {
      padding: 12px 0;

      &.overview-panel .section-title {
        margin: 16px 0 8px;
      }
    }

    :deep(.t-form__item) {
      flex-direction: column;
    }

    :deep(.t-form__label) {
      width: 100% !important;
      text-align: left !important;
      padding-right: 0 !important;
      margin-bottom: 4px;
    }

    :deep(.t-form__controls) {
      margin-left: 0 !important;
      width: 100%;
    }
  }
}
</style>
