<template>
  <div class="model-settings">
    <t-card :title="$t('pages.aiVoice.admin.modelSettings.title')">
      <t-form :data="formData" label-width="180px" @submit="handleSubmit" @reset="handleReset">
        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.modelProvider')">
          <t-select
            v-model="formData.provider"
            :options="providerOptions"
            placeholder="Select model provider"
            @change="handleProviderChange"
          />
        </t-form-item>

        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.modelName')">
          <t-select
            v-model="formData.modelName"
            :options="modelOptions"
            placeholder="Select model"
            :disabled="!formData.provider"
          />
        </t-form-item>

        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.apiKey')">
          <t-input
            v-model="formData.apiKey"
            type="password"
            placeholder="Enter API key"
            clearable
          />
        </t-form-item>

        <t-divider>{{ $t('pages.aiVoice.admin.modelSettings.advancedSettings') }}</t-divider>

        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.temperature')">
          <t-slider
            v-model="formData.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            :marks="{ 0: '0', 1: '1', 2: '2' }"
          />
          <div class="slider-value">{{ formData.temperature }}</div>
        </t-form-item>

        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.maxTokens')">
          <t-input-number
            v-model="formData.maxTokens"
            :min="1"
            :max="4096"
            placeholder="Enter max tokens"
          />
        </t-form-item>

        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.topP')">
          <t-slider
            v-model="formData.topP"
            :min="0"
            :max="1"
            :step="0.01"
            :marks="{ 0: '0', 0.5: '0.5', 1: '1' }"
          />
          <div class="slider-value">{{ formData.topP }}</div>
        </t-form-item>

        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.frequencyPenalty')">
          <t-slider
            v-model="formData.frequencyPenalty"
            :min="-2"
            :max="2"
            :step="0.1"
            :marks="{ '-2': '-2', 0: '0', 2: '2' }"
          />
          <div class="slider-value">{{ formData.frequencyPenalty }}</div>
        </t-form-item>

        <t-form-item :label="$t('pages.aiVoice.admin.modelSettings.presencePenalty')">
          <t-slider
            v-model="formData.presencePenalty"
            :min="-2"
            :max="2"
            :step="0.1"
            :marks="{ '-2': '-2', 0: '0', 2: '2' }"
          />
          <div class="slider-value">{{ formData.presencePenalty }}</div>
        </t-form-item>

        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit">
              {{ $t('pages.aiVoice.admin.modelSettings.save') }}
            </t-button>
            <t-button theme="default" type="reset">
              {{ $t('pages.aiVoice.admin.modelSettings.cancel') }}
            </t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { MessagePlugin } from 'tdesign-vue-next';
import { ref, reactive, computed, onMounted } from 'vue';

import { ModelService } from '@/api/ModelService';
import { t } from '@/locales';

const modelService = new ModelService();

const openaiLabel = 'OpenAI';
const providerOptions = [
  { label: openaiLabel, value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Google', value: 'google' },
];

const openaiModels = [
  { label: 'gpt-4', value: 'gpt-4' },
  { label: 'gpt-4-turbo', value: 'gpt-4-turbo' },
  { label: 'gpt-3.5-turbo', value: 'gpt-3.5-turbo' },
];

const anthropicModels = [
  { label: 'claude-3-opus', value: 'claude-3-opus' },
  { label: 'claude-3-sonnet', value: 'claude-3-sonnet' },
  { label: 'claude-3-haiku', value: 'claude-3-haiku' },
];

const googleModels = [
  { label: 'gemini-pro', value: 'gemini-pro' },
  { label: 'gemini-ultra', value: 'gemini-ultra' },
];

const modelOptions = computed((): Array<{ label: string; value: string }> => {
  switch (formData.provider) {
    case 'openai':
      return openaiModels;
    case 'anthropic':
      return anthropicModels;
    case 'google':
      return googleModels;
    default:
      return [];
  }
});

const formData = reactive({
  provider: 'openai',
  modelName: 'gpt-4',
  apiKey: '',
  temperature: 0.7,
  maxTokens: 2000,
  topP: 1.0,
  frequencyPenalty: 0,
  presencePenalty: 0,
});

const handleProviderChange = () => {
  // Reset model name when provider changes
  const models = modelOptions.value;
  if (models.length > 0) {
    formData.modelName = models[0].value;
  }
};

const handleSubmit = async () => {
  try {
    await modelService.updateModelSettings(formData);
    MessagePlugin.success(t('pages.aiVoice.admin.modelSettings.saveSuccess'));
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.modelSettings.saveFailed'));
  }
};

const handleReset = () => {
  formData.provider = 'openai';
  formData.modelName = 'gpt-4';
  formData.apiKey = '';
  formData.temperature = 0.7;
  formData.maxTokens = 2000;
  formData.topP = 1.0;
  formData.frequencyPenalty = 0;
  formData.presencePenalty = 0;
};

// Load current settings on mount
const loadSettings = async () => {
  try {
    const settings: any = await modelService.getModelSettings();
    if (settings) {
      formData.provider = settings.provider || 'openai';
      formData.modelName = settings.modelName || 'gpt-4';
      formData.apiKey = settings.apiKey || '';
      formData.temperature = settings.temperature || 0.7;
      formData.maxTokens = settings.maxTokens || 2000;
      formData.topP = settings.topP || 1.0;
      formData.frequencyPenalty = settings.frequencyPenalty || 0;
      formData.presencePenalty = settings.presencePenalty || 0;
      
      if (settings.availableModels) {
        const providerModels = (settings.availableModels as any)[formData.provider];
        if (providerModels && Array.isArray(providerModels) && providerModels.length > 0) {
          const found = providerModels.find((m: any) => m.value === formData.modelName);
          if (!found) {
            formData.modelName = providerModels[0].value;
          }
        }
      }
    }
  } catch (error) {
    MessagePlugin.error('Failed to load model settings');
  }
};

onMounted(() => {
  loadSettings();
});
</script>

<style scoped lang="less">
.model-settings {
  padding: 24px;

  :deep(.t-form) {
    padding: 24px;
  }

  .slider-value {
    text-align: center;
    margin-top: 8px;
    font-weight: bold;
    color: var(--td-text-color-primary);
  }
}
</style>

