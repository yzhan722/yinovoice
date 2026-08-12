<template>
  <div class="assistant-detail">
    <t-card :title="t('pages.aiVoice.admin.assistantList.assistantDetail')">
      <template #actions>
        <t-space>
          <t-button theme="default" @click="handleBack">
            {{ t('pages.aiVoice.admin.assistantList.back') }}
          </t-button>
        </t-space>
      </template>

      <div v-if="loading" class="loading-container">
        <t-loading />
      </div>

      <div v-else-if="assistantData" class="detail-content">
        <t-tabs v-model="activeTab" @change="handleTabChange">
          <!-- 基本信息 Tab -->
          <t-tab-panel value="basic" :label="t('pages.aiVoice.admin.assistantList.basicInfo')">
            <div class="settings-content">
              <t-form :data="basicFormData" label-width="200px" @submit="handleBasicSubmit">
                <t-row :gutter="24">
                  <t-col :span="12">
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.assistantId')">
                      <t-tag theme="default">{{ assistantData?.attVendorId }}</t-tag>
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.assistantName')">
                      <t-input v-model="basicFormData.attName" :placeholder="t('pages.aiVoice.admin.assistantList.assistantNamePlaceholder')" />
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.status')">
                      <t-select v-model="basicFormData.attStatus" :options="statusOptions" />
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.createTime')">
                      <t-input :value="formatDateTime(assistantData?.attCreateTime)" readonly />
                    </t-form-item>
                    <t-form-item :label="t('pages.aiVoice.admin.assistantList.updateTime')">
                      <t-input :value="formatDateTime(assistantData?.attUpdateTime)" readonly />
                    </t-form-item>
                  </t-col>

                  <t-col :span="12">
                    <div class="assigned-user-section">
                      <h4>{{ t('pages.aiVoice.admin.assistantList.assignedUser') }}</h4>
                      <div class="assigned-user-card">
                        <div v-if="assignedUser" class="user-info">
                          <div class="user-avatar">
                            <t-avatar v-if="assignedUser.userAvatar" :image="assignedUser.userAvatar" size="large" />
                            <t-avatar v-else size="large">{{ assignedUser.userNickname?.charAt(0) || 'U' }}</t-avatar>
                          </div>
                          <div class="user-details">
                            <div class="user-name">{{ assignedUser.userNickname }}</div>
                            <div class="user-account">{{ assignedUser.userAccount }}</div>
                            <div class="user-mobile" v-if="assignedUser.userMobile">{{ assignedUser.userMobile }}</div>
                          </div>
                          <div class="user-actions">
                            <t-button size="small" theme="primary" @click="handleViewUser">
                              {{ t('pages.aiVoice.admin.assistantList.viewUser') }}
                            </t-button>
                            <t-button size="small" theme="default" @click="handleChangeUser">
                              {{ t('pages.aiVoice.admin.assistantList.changeUser') }}
                            </t-button>
                          </div>
                        </div>
                        <div v-else class="no-user">
                          <div class="no-user-text">{{ t('pages.aiVoice.admin.assistantList.noCurrentUser') }}</div>
                          <t-button theme="primary" @click="handleAssignUser">
                            {{ t('pages.aiVoice.admin.assistantList.assignUser') }}
                          </t-button>
                        </div>
                      </div>
                    </div>
                  </t-col>
                </t-row>
                
                <t-form-item>
                  <t-space>
                    <t-button theme="primary" type="submit">
                      {{ t('pages.aiVoice.admin.assistantList.save') }}
                    </t-button>
                    <t-button theme="default" @click="handleBasicReset">
                      {{ t('pages.aiVoice.admin.assistantList.reset') }}
                    </t-button>
                  </t-space>
                </t-form-item>
              </t-form>
            </div>
          </t-tab-panel>

          <!-- 模型配置 Tab -->
          <t-tab-panel value="model" :label="t('pages.aiVoice.admin.assistantList.modelConfig')">
            <div class="settings-content">
              <t-form :data="modelFormData" label-width="200px" @submit="handleModelSubmit">
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.modelProvider')">
                  <t-select
                    v-model="modelFormData.provider"
                    :options="modelProviderOptions"
                    :placeholder="t('pages.aiVoice.admin.assistantList.pleaseSelect')"
                    @change="handleModelProviderChange"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.modelName')">
                  <t-select
                    v-model="modelFormData.model"
                    :options="modelOptions"
                    :placeholder="t('pages.aiVoice.admin.assistantList.pleaseSelect')"
                    :disabled="!modelFormData.provider"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.temperature')">
                  <t-slider
                    v-model="modelFormData.temperature"
                    :min="0"
                    :max="2"
                    :step="0.1"
                    :marks="{ 0: '0', 1: '1', 2: '2' }"
                  />
                  <div class="slider-value">{{ modelFormData.temperature }}</div>
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.maxTokens')">
                  <t-input-number
                    v-model="modelFormData.maxTokens"
                    :min="1"
                    :max="8192"
                    :placeholder="t('pages.aiVoice.admin.assistantList.maxTokensPlaceholder')"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.adminSystemPrompt')">
                  <t-textarea 
                    v-model="modelFormData.systemMessage"
                    :autosize="{ minRows: 10, maxRows: 20 }"
                    :placeholder="t('pages.aiVoice.admin.assistantList.systemPromptPlaceholder')"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.userSystemPrompt')">
                  <t-textarea 
                    v-model="modelFormData.userSystemMessage"
                    :autosize="{ minRows: 10, maxRows: 20 }"
                    :placeholder="t('pages.aiVoice.admin.assistantList.userSystemPromptPlaceholder')"
                  />
                </t-form-item>
                
                <t-form-item>
                  <t-space>
                    <t-button theme="primary" type="submit">
                      {{ t('pages.aiVoice.admin.assistantList.save') }}
                    </t-button>
                    <t-button theme="default" @click="handleModelReset">
                      {{ t('pages.aiVoice.admin.assistantList.reset') }}
                    </t-button>
                  </t-space>
                </t-form-item>
              </t-form>
            </div>
          </t-tab-panel>

          <!-- 语音配置 Tab -->
          <t-tab-panel value="voice" :label="t('pages.aiVoice.admin.assistantList.voiceConfig')">
            <div class="settings-content">
              <t-form :data="voiceFormData" label-width="200px" @submit="handleVoiceSubmit">
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.voiceProvider')">
                  <t-input value="11Labs" disabled />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.voiceId')">
                  <t-space>
                    <t-input
                      v-model="selectedVoiceName"
                      :placeholder="t('pages.aiVoice.admin.assistantList.pleaseSelect')"
                      readonly
                      style="width: 300px"
                    />
                    <t-button theme="primary" @click="openVoiceDialog">
                      {{ t('pages.aiVoice.admin.assistantList.selectVoice') }}
                    </t-button>
                  </t-space>
                </t-form-item>
                <t-form-item 
                  v-if="voiceFormData.provider === '11labs'" 
                  :label="t('pages.aiVoice.admin.assistantList.voiceModel')"
                >
                  <t-select
                    v-model="voiceFormData.model"
                    :options="elevenLabsModelOptions"
                    :placeholder="t('pages.aiVoice.admin.assistantList.pleaseSelect')"
                  >
                    <template #option="{ option }">
                      <div>
                        <div class="model-name">{{ option.label }}</div>
                        <div class="model-description">{{ option.description }}</div>
                      </div>
                    </template>
                  </t-select>
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.stability')">
                  <t-slider
                    v-model="voiceFormData.stability"
                    :min="0"
                    :max="1"
                    :step="0.01"
                    :marks="{ 0: '0', 0.5: '0.5', 1: '1.0' }"
                  />
                  <div class="slider-value">{{ voiceFormData.stability }}</div>
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.similarityBoost')">
                  <t-slider
                    v-model="voiceFormData.similarityBoost"
                    :min="0"
                    :max="1"
                    :step="0.01"
                    :marks="{ 0: '0', 0.5: '0.5', 1: '1.0' }"
                  />
                  <div class="slider-value">{{ voiceFormData.similarityBoost }}</div>
                </t-form-item>
                
                <t-form-item>
                  <t-space>
                    <t-button theme="primary" type="submit">
                      {{ t('pages.aiVoice.admin.assistantList.save') }}
                    </t-button>
                    <t-button theme="default" @click="handleVoiceReset">
                      {{ t('pages.aiVoice.admin.assistantList.reset') }}
                    </t-button>
                  </t-space>
                </t-form-item>
              </t-form>
            </div>
          </t-tab-panel>

          <!-- 转录配置 Tab -->
          <t-tab-panel value="transcriber" :label="t('pages.aiVoice.admin.assistantList.transcriberConfig')">
            <div class="settings-content">
              <t-form :data="transcriberFormData" label-width="200px" @submit="handleTranscriberSubmit">
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.transcriberProvider')">
                  <t-select
                    v-model="transcriberFormData.provider"
                    :options="transcriberProviderOptions"
                    :placeholder="t('pages.aiVoice.admin.assistantList.pleaseSelect')"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.transcriberModel')">
                  <t-input v-model="transcriberFormData.model" :placeholder="t('pages.aiVoice.admin.assistantList.transcriberModelPlaceholder')" />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.transcriberLanguage')">
                  <t-select
                    v-model="transcriberFormData.language"
                    :options="[
                      { label: 'English', value: 'en' },
                      { label: 'Chinese', value: 'zh' },
                      { label: 'Spanish', value: 'es' },
                      { label: 'French', value: 'fr' },
                      { label: 'German', value: 'de' },
                    ]"
                    :placeholder="t('pages.aiVoice.admin.assistantList.pleaseSelect')"
                  />
                </t-form-item>
                
                <t-form-item>
                  <t-space>
                    <t-button theme="primary" type="submit">
                      {{ t('pages.aiVoice.admin.assistantList.save') }}
                    </t-button>
                    <t-button theme="default" @click="handleTranscriberReset">
                      {{ t('pages.aiVoice.admin.assistantList.reset') }}
                    </t-button>
                  </t-space>
                </t-form-item>
              </t-form>
            </div>
          </t-tab-panel>

          <!-- 消息配置 Tab -->
          <t-tab-panel value="messages" :label="t('pages.aiVoice.admin.assistantList.messageConfig')">
            <div class="settings-content">
              <t-form :data="messageFormData" label-width="200px" @submit="handleMessageSubmit">
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.firstMessage')">
                  <t-textarea 
                    v-model="messageFormData.firstMessage"
                    :autosize="{ minRows: 3, maxRows: 6 }"
                    :placeholder="t('pages.aiVoice.admin.assistantList.firstMessagePlaceholder')"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.voicemailMessage')">
                  <t-textarea 
                    v-model="messageFormData.voicemailMessage"
                    :autosize="{ minRows: 3, maxRows: 6 }"
                    :placeholder="t('pages.aiVoice.admin.assistantList.voicemailMessagePlaceholder')"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.endCallMessage')">
                  <t-textarea 
                    v-model="messageFormData.endCallMessage"
                    :autosize="{ minRows: 3, maxRows: 6 }"
                    :placeholder="t('pages.aiVoice.admin.assistantList.endCallMessagePlaceholder')"
                  />
                </t-form-item>
                <t-form-item :label="t('pages.aiVoice.admin.assistantList.forwardingPhone')">
                  <t-input v-model="messageFormData.forwardingPhone" :placeholder="t('pages.aiVoice.admin.assistantList.forwardingPhonePlaceholder')" />
                </t-form-item>
                
                <t-form-item>
                  <t-space>
                    <t-button theme="primary" type="submit">
                      {{ t('pages.aiVoice.admin.assistantList.save') }}
                    </t-button>
                    <t-button theme="default" @click="handleMessageReset">
                      {{ t('pages.aiVoice.admin.assistantList.reset') }}
                    </t-button>
                  </t-space>
                </t-form-item>
              </t-form>
            </div>
          </t-tab-panel>

          <!-- 高级配置 Tab -->
          <t-tab-panel value="advanced" :label="t('pages.aiVoice.admin.assistantList.advancedConfig')">
            <div class="settings-content">
              <t-descriptions :column="2" bordered>
                <t-descriptions-item :label="t('pages.aiVoice.admin.assistantList.serverUrlSecretSet')">
                  <t-tag :theme="assistantData.attIsServerUrlSecretSet ? 'success' : 'warning'">
                    {{ assistantData.attIsServerUrlSecretSet ? 'Yes' : 'No' }}
                  </t-tag>
                </t-descriptions-item>
                <t-descriptions-item :label="t('pages.aiVoice.admin.assistantList.createUser')">
                  {{ assistantData.attCreateUser || '-' }}
                </t-descriptions-item>
                <t-descriptions-item :label="t('pages.aiVoice.admin.assistantList.updateUser')">
                  {{ assistantData.attUpdateUser || '-' }}
                </t-descriptions-item>
              </t-descriptions>

              <!-- Artifact Plan -->
              <div v-if="artifactPlan" class="artifact-plan-section">
                <h4>{{ t('pages.aiVoice.admin.assistantList.artifactPlan') }}</h4>
                <t-descriptions :column="1" bordered>
                  <t-descriptions-item :label="t('pages.aiVoice.admin.assistantList.structuredOutputIds')">
                    <t-tag v-for="id in artifactPlan.structuredOutputIds" :key="id" class="output-id-tag">{{ id }}</t-tag>
                  </t-descriptions-item>
                  <t-descriptions-item :label="t('pages.aiVoice.admin.assistantList.scorecardIds')">
                    <t-tag v-for="id in artifactPlan.scorecardIds" :key="id" class="scorecard-id-tag">{{ id }}</t-tag>
                  </t-descriptions-item>
                </t-descriptions>
              </div>

              <!-- Server Config -->
              <div class="server-config-section">
                <h4>{{ t('pages.aiVoice.admin.assistantList.serverConfig') }}</h4>
                <t-form :data="serverFormData" label-width="200px" @submit="handleServerSubmit">
                  <t-form-item :label="t('pages.aiVoice.admin.assistantList.serverUrl')">
                    <t-input 
                      v-model="serverFormData.url" 
                      :placeholder="t('pages.aiVoice.admin.assistantList.serverUrlPlaceholder')" 
                    />
                  </t-form-item>
                  <t-form-item :label="t('pages.aiVoice.admin.assistantList.serverTimeout')">
                    <t-input-number
                      v-model="serverFormData.timeoutSeconds"
                      :min="1"
                      :max="300"
                      :placeholder="t('pages.aiVoice.admin.assistantList.serverTimeoutPlaceholder')"
                    />
                    <span class="timeout-unit">seconds</span>
                  </t-form-item>
                  
                  <t-form-item>
                    <t-space>
                      <t-button theme="primary" type="submit">
                        {{ t('pages.aiVoice.admin.assistantList.save') }}
                      </t-button>
                      <t-button theme="default" @click="handleServerReset">
                        {{ t('pages.aiVoice.admin.assistantList.reset') }}
                      </t-button>
                    </t-space>
                  </t-form-item>
                </t-form>
              </div>
            </div>
          </t-tab-panel>
        </t-tabs>
      </div>
    </t-card>

    <!-- 用户分配弹窗 -->
    <t-dialog 
      v-model:visible="assignDialogVisible" 
      :header="t('pages.aiVoice.admin.assistantList.assignUser')"
      width="900px"
      @confirm="handleAssignConfirm"
      @cancel="handleAssignCancel"
    >
      <template #body>
        <!-- 用户搜索 -->
        <t-form @submit="handleUserSearch" class="user-search-form">
          <div class="user-search-row">
            <t-form-item :label="t('pages.aiVoice.admin.assistantList.userAccount')" class="user-search-item">
              <t-input v-model="userSearchForm.userAccount" :placeholder="t('pages.aiVoice.admin.assistantList.userAccountPlaceholder')" clearable />
            </t-form-item>
            <t-form-item :label="t('pages.aiVoice.admin.assistantList.userMobile')" class="user-search-item">
              <t-input v-model="userSearchForm.userMobile" :placeholder="t('pages.aiVoice.admin.assistantList.userMobilePlaceholder')" clearable />
            </t-form-item>
            <div class="user-search-actions">
              <t-space>
                <t-button theme="primary" type="submit">
                  {{ t('pages.aiVoice.admin.assistantList.search') }}
                </t-button>
                <t-button theme="default" @click="handleUserSearchReset">
                  {{ t('pages.aiVoice.admin.assistantList.reset') }}
                </t-button>
              </t-space>
            </div>
          </div>
        </t-form>

        <!-- 用户列表 -->
        <div class="user-list-container">
          <t-table
            :data="userList"
            :columns="userColumns"
            :loading="userListLoading"
            row-key="userId"
            @select-change="handleUserSelect"
            :selected-row-keys="selectedUserIds"
            :select-on-row-click="true"
          >
            <template #userAvatar="{ row }">
              <t-avatar v-if="row.userAvatar" :image="row.userAvatar" size="medium" />
              <t-avatar v-else size="medium">{{ row.userNickname?.charAt(0) || 'U' }}</t-avatar>
            </template>
          </t-table>
          <div class="top-items-hint">
            {{ t('pages.aiVoice.admin.assistantList.top10Items') }}
          </div>
        </div>
      </template>
    </t-dialog>

    <!-- Voice 选择弹窗 -->
    <t-dialog
      v-model:visible="voiceDialogVisible"
      :header="t('pages.aiVoice.admin.assistantList.selectVoice')"
      width="800px"
      :footer="false"
    >
      <div class="voice-dialog-content">
        <div class="voice-toolbar">
          <t-button theme="primary" @click="handleCreateVoice">
            {{ t('pages.aiVoice.admin.assistantList.create') }}
          </t-button>
        </div>
        <t-table
          :data="voiceList"
          :columns="voiceColumns"
          :loading="voiceListLoading"
          row-key="diyId"
        >
          <template #diyStatus="{ row }">
            <t-tag :theme="row.diyStatus === 1 ? 'success' : 'default'" variant="light">
              {{ row.diyStatus === 1 ? t('pages.aiVoice.admin.assistantList.enabled') : t('pages.aiVoice.admin.assistantList.disabled') }}
            </t-tag>
          </template>
          <template #op="{ row }">
            <t-space>
              <t-link theme="primary" @click="handleSelectVoice(row)">
                {{ t('pages.aiVoice.admin.assistantList.select') }}
              </t-link>
              <t-link theme="primary" @click="handleEditVoice(row)">
                {{ t('pages.aiVoice.admin.assistantList.edit') }}
              </t-link>
              <t-link theme="danger" @click="handleDeleteVoice(row)">
                {{ t('pages.aiVoice.admin.assistantList.delete') }}
              </t-link>
            </t-space>
          </template>
        </t-table>
      </div>
    </t-dialog>

    <!-- Voice 表单弹窗 -->
    <t-dialog
      v-model:visible="voiceFormDialogVisible"
      :header="voiceFormDataDialog.diyId ? t('pages.aiVoice.admin.assistantList.edit') : t('pages.aiVoice.admin.assistantList.create')"
      width="600px"
      @confirm="handleVoiceFormSubmit"
    >
      <t-form :data="voiceFormDataDialog" label-width="120px">
        <t-form-item :label="t('pages.aiVoice.admin.assistantList.voiceName')" name="diyName">
          <t-input v-model="voiceFormDataDialog.diyName" :placeholder="t('pages.aiVoice.admin.assistantList.voiceNamePlaceholder')" />
        </t-form-item>
        <t-form-item :label="t('pages.aiVoice.admin.assistantList.voiceCode')" name="diyCode">
          <t-input v-model="voiceFormDataDialog.diyCode" :placeholder="t('pages.aiVoice.admin.assistantList.voiceCodePlaceholder')" />
        </t-form-item>
        <t-form-item :label="t('pages.aiVoice.admin.assistantList.voiceDesc')" name="diyDesc">
          <t-textarea v-model="voiceFormDataDialog.diyDesc" :placeholder="t('pages.aiVoice.admin.assistantList.voiceDescPlaceholder')" :autosize="{ minRows: 3, maxRows: 5 }" />
        </t-form-item>
        <t-form-item :label="t('pages.aiVoice.admin.assistantList.voiceStatus')" name="diyStatus">
          <t-select v-model="voiceFormDataDialog.diyStatus">
            <t-option :value="1" :label="t('pages.aiVoice.admin.assistantList.enabled')" />
            <t-option :value="0" :label="t('pages.aiVoice.admin.assistantList.disabled')" />
          </t-select>
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { MessagePlugin, DialogPlugin, PrimaryTableCol } from 'tdesign-vue-next';
import { ref, reactive, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { OperatorInstanceService as AdminAssistantService } from '@/api/platform';
import { DictionaryService } from '@/api/DictionaryService';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const route = useRoute();
const router = useRouter();
const adminAssistantService = new AdminAssistantService();
const dictionaryService = new DictionaryService();

const loading = ref(false);
const assistantData = ref<any>(null);
const assignedUser = ref<any>(null);
const activeTab = ref('basic');

interface ArtifactPlan {
  structuredOutputIds: string[];
  scorecardIds: string[];
}

const artifactPlan = computed<ArtifactPlan | null>(() => {
  const raw = assistantData.value?.attArtifactPlan ?? assistantData.value?.artifactPlan;
  if (!raw) return null;

  try {
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    return {
      structuredOutputIds: Array.isArray(parsed.structuredOutputIds)
        ? parsed.structuredOutputIds
        : [],
      scorecardIds: Array.isArray(parsed.scorecardIds) ? parsed.scorecardIds : [],
    };
  } catch {
    return null;
  }
});

// 表单数据
const basicFormData = reactive({
  attName: '',
  attStatus: 1,
});

const voiceFormData = reactive({
  provider: '11labs', // 固定为 11Labs
  voiceId: '',
  model: '', // 仅11Labs使用
  stability: 0.5,
  similarityBoost: 0.75,
});

// Voice 选择弹窗相关
const voiceDialogVisible = ref(false);
const voiceList = ref([]);
const voiceListLoading = ref(false);
const selectedVoiceName = ref('');
const voiceFormDialogVisible = ref(false);
const voiceFormDataDialog = reactive({
  diyId: null,
  diyName: '',
  diyCode: '',
  diyDesc: '',
  diyStatus: 1,
});

const modelFormData = reactive({
  provider: '',
  model: '',
  temperature: 0.7,
  maxTokens: 2000,
  systemMessage: '', // 管理员 System Prompt
  userSystemMessage: '', // 用户 System Prompt
  toolIds: [],
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

const serverFormData = reactive({
  url: '',
  timeoutSeconds: 20,
});

// 弹窗状态
const assignDialogVisible = ref(false);

// 选择器选项
const modelProviderOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Google', value: 'google' },
  { label: 'DeepSeek', value: 'deepseek' },
];

const modelOptionsMap: Record<string, Array<{ label: string; value: string }>> = {
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

const voiceOptionsMap: Record<string, Array<{ label: string; value: string }>> = {
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

const transcriberProviderOptions = [
  { label: 'Deepgram', value: 'deepgram' },
  { label: 'Assembly AI', value: 'assembly-ai' },
];

const statusOptions = [
  { label: t('pages.aiVoice.admin.assistantList.enabled'), value: 1 },
  { label: t('pages.aiVoice.admin.assistantList.disabled'), value: 0 },
];

// 计算属性
const modelOptions = computed(() => {
  return modelOptionsMap[modelFormData.provider] || [];
});

const voiceOptions = computed(() => {
  return voiceOptionsMap[voiceFormData.provider] || [];
});

// 11Labs模型选项
const elevenLabsModelOptions = [
  { 
    label: 'Eleven Multilingual v2', 
    value: 'eleven_multilingual_v2',
    description: 'Our state of the art multilingual speech synthesis model, able to generate life-like speech in 29 languages.'
  },
  { 
    label: 'Eleven Turbo v2', 
    value: 'eleven_turbo_v2',
    description: 'Our cutting-edge turbo model is ideally suited for tasks demanding extremely low latency.'
  },
  { 
    label: 'Eleven Turbo v2.5', 
    value: 'eleven_turbo_v2_5',
    description: 'Our cutting-edge turbo model is ideally suited for tasks demanding extremely low latency.'
  },
  { 
    label: 'Eleven Flash v2', 
    value: 'eleven_flash_v2',
    description: 'Our newest model, Flash, generates speech in ~75ms (excluding network/application latency).'
  },
  { 
    label: 'Eleven Flash v2.5', 
    value: 'eleven_flash_v2_5',
    description: 'Our newest model, Flash, generates speech in ~75ms (excluding network/application latency).'
  },
  { 
    label: 'Eleven English v1', 
    value: 'eleven_monolingual_v1',
    description: 'Use our standard English language model to generate speech in a variety of voices, styles and moods.'
  },
];

// 用户搜索
const userSearchForm = reactive({
  userAccount: '',
  userMobile: '',
});
const userList = ref([]);
const userListLoading = ref(false);
const selectedUserIds = ref([]);

const voiceColumns: PrimaryTableCol[] = [
  {
    title: t('pages.aiVoice.admin.assistantList.voiceName'),
    colKey: 'diyName',
    width: 150,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.voiceCode'),
    colKey: 'diyCode',
    width: 150,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.voiceDesc'),
    colKey: 'diyDesc',
    width: 200,
    ellipsis: true,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.voiceStatus'),
    colKey: 'diyStatus',
    width: 100,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.actions'),
    colKey: 'op',
    width: 200,
    fixed: 'right',
  },
];

const userColumns: PrimaryTableCol[] = [
  {
    colKey: 'row-select',
    type: 'single',
    width: 60,
    checkProps: { allowUncheck: true },
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userAvatar'),
    colKey: 'userAvatar',
    width: 100,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userNickname'),
    colKey: 'userNickname',
    width: 120,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userAccount'),
    colKey: 'userAccount',
    width: 200,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userMobile'),
    colKey: 'userMobile',
    width: 150,
  },
];

const handleTabChange = (value: string) => {
  activeTab.value = value;
};

const handleBack = () => {
  router.push('/admin/assistant-list');
};

const handleViewUser = () => {
  if (assignedUser.value && assignedUser.value.userId) {
    router.push(`/admin/user-manager/detail/${assignedUser.value.userId}`);
  }
};

const handleChangeUser = () => {
  assignDialogVisible.value = true;
  loadUserList();
};

const handleAssignUser = () => {
  assignDialogVisible.value = true;
  loadUserList();
};

const handleUserSearch = async () => {
  await loadUserList();
};

const handleUserSearchReset = () => {
  userSearchForm.userAccount = '';
  userSearchForm.userMobile = '';
  loadUserList();
};

const handleUserSelect = (selectedRowKeys: any[]) => {
  selectedUserIds.value = selectedRowKeys;
};

const handleAssignConfirm = async () => {
  if (selectedUserIds.value.length === 0) {
    MessagePlugin.warning(t('pages.aiVoice.admin.assistantList.pleaseSelectUser'));
    return;
  }

  try {
    const selectedUser = userList.value.find(user => user.userId === selectedUserIds.value[0]);
    await adminAssistantService.assignAssistant({
      attId: assistantData.value.attId,
      userId: selectedUser.userId
    });
    
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.assignSuccess'));
    assignDialogVisible.value = false;
    selectedUserIds.value = [];
    
    // 重新加载数据
    await loadAssistantDetail();
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.assignFailed'));
  }
};

const handleAssignCancel = () => {
  assignDialogVisible.value = false;
  selectedUserIds.value = [];
  userSearchForm.userAccount = '';
  userSearchForm.userMobile = '';
};

const loadUserList = async () => {
  userListLoading.value = true;
  try {
    const searchTerm = userSearchForm.userAccount || userSearchForm.userMobile;
    const response = await adminAssistantService.searchUsers(searchTerm);
    userList.value = response;
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.loadUsersFailed'));
  } finally {
    userListLoading.value = false;
  }
};

const loadAssistantDetail = async () => {
  const attId = route.params.attId;
  if (!attId) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.invalidAssistantId'));
    return;
  }

  loading.value = true;
  try {
    const response = await adminAssistantService.getAssistantDetail({ attId: Number(attId) });
    assistantData.value = response;
    
    // 设置分配用户信息
    assignedUser.value = response.assignedUser || null;
    
    // 解析JSON配置
    parseConfigurations(response);
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.loadDetailFailed'));
  } finally {
    loading.value = false;
  }
};

const parseConfigurations = (data: any) => {
  try {
    // 填充基本信息表单
    basicFormData.attName = data.attName || '';
    basicFormData.attStatus = data.attStatus || 1;

    // 解析语音配置
    if (data.attVoiceConfig) {
      const voiceData = JSON.parse(data.attVoiceConfig);
      voiceFormData.provider = '11labs'; // 固定为 11Labs
      voiceFormData.voiceId = voiceData.voiceId || '';
      voiceFormData.model = voiceData.model || ''; // 只有11Labs才有这个字段
      voiceFormData.stability = voiceData.stability || 0.5;
      voiceFormData.similarityBoost = voiceData.similarityBoost || 0.75;
      
      // 加载 Voice 列表并设置选中的名称
      if (voiceFormData.voiceId) {
        loadVoiceList().then(() => {
          const selectedVoice = voiceList.value.find((v: any) => v.diyCode === voiceFormData.voiceId);
          // 如果找不到匹配的 voice，显示 voiceId 本身
          selectedVoiceName.value = selectedVoice ? selectedVoice.diyName : voiceFormData.voiceId;
        });
      }
    }
    
    // 解析模型配置
    if (data.attModelConfig) {
      const modelData = JSON.parse(data.attModelConfig);
      modelFormData.provider = modelData.provider || '';
      modelFormData.model = modelData.model || '';
      modelFormData.temperature = modelData.temperature || 0.7;
      modelFormData.maxTokens = modelData.maxTokens || 2000;
      modelFormData.toolIds = modelData.toolIds || [];
    }
    
    // 从后端返回的分离字段填充 System Prompt
    modelFormData.systemMessage = data.adminSystemPrompt || '';
    modelFormData.userSystemMessage = data.userSystemPrompt || '';
    
    // 解析转录配置
    if (data.attTranscriberConfig) {
      const transcriberData = JSON.parse(data.attTranscriberConfig);
      transcriberFormData.provider = transcriberData.provider || '';
      transcriberFormData.model = transcriberData.model || '';
      transcriberFormData.language = transcriberData.language || 'en';
    }

    // 填充消息表单
    messageFormData.firstMessage = data.attFirstMessage || '';
    messageFormData.voicemailMessage = data.attVoicemailMessage || '';
    messageFormData.endCallMessage = data.attEndCallMessage || '';
    messageFormData.forwardingPhone = data.attForwardingPhone || '';

    // 解析server配置（从compliance_plan中）
    if (data.attCompliancePlan) {
      try {
        const complianceData = JSON.parse(data.attCompliancePlan);
        if (complianceData.server) {
          serverFormData.url = complianceData.server.url || '';
          serverFormData.timeoutSeconds = complianceData.server.timeoutSeconds || 20;
        }
      } catch (error) {
        console.warn('Failed to parse compliance plan:', error);
      }
    }
  } catch (error) {
    console.warn('Failed to parse JSON configurations:', error);
  }
};

// 表单处理函数
const handleBasicSubmit = async () => {
  try {
    await updateAssistant({
      attId: assistantData.value.attId,
      attName: basicFormData.attName,
      attStatus: basicFormData.attStatus,
    });
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.saveSuccess'));
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.saveFailed'));
  }
};

const handleVoiceSubmit = async () => {
  try {
    const voiceConfig: {
      provider: string;
      voiceId: string;
      stability: number;
      similarityBoost: number;
      model?: string;
    } = {
      provider: voiceFormData.provider,
      voiceId: voiceFormData.voiceId,
      stability: voiceFormData.stability,
      similarityBoost: voiceFormData.similarityBoost,
    };
    
    // 只有11Labs才包含model字段
    if (voiceFormData.provider === '11labs') {
      voiceConfig.model = voiceFormData.model;
    }
    
    await updateAssistant({
      attId: assistantData.value.attId,
      attVoiceConfig: JSON.stringify(voiceConfig),
    });
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.saveSuccess'));
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.saveFailed'));
  }
};

const handleModelSubmit = async () => {
  try {
    // 传递分离的 System Prompt 字段，后端会自动合并
    await updateAssistant({
      attId: assistantData.value.attId,
      adminSystemPrompt: modelFormData.systemMessage,
      userSystemPrompt: modelFormData.userSystemMessage,
      // 同时传递其他 model 配置字段（如果需要更新的话）
      attModelConfig: assistantData.value.attModelConfig, // 保持其他配置不变
    });
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.saveSuccess'));
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.saveFailed'));
  }
};

const handleTranscriberSubmit = async () => {
  try {
    const transcriberConfig = {
      provider: transcriberFormData.provider,
      model: transcriberFormData.model,
      language: transcriberFormData.language,
    };
    
    await updateAssistant({
      attId: assistantData.value.attId,
      attTranscriberConfig: JSON.stringify(transcriberConfig),
    });
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.saveSuccess'));
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.saveFailed'));
  }
};

const handleMessageSubmit = async () => {
  try {
    await updateAssistant({
      attId: assistantData.value.attId,
      attFirstMessage: messageFormData.firstMessage,
      attVoicemailMessage: messageFormData.voicemailMessage,
      attEndCallMessage: messageFormData.endCallMessage,
      attForwardingPhone: messageFormData.forwardingPhone,
    });
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.saveSuccess'));
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.saveFailed'));
  }
};

const handleServerSubmit = async () => {
  try {
    const compliancePlan = {
      server: {
        url: serverFormData.url,
        timeoutSeconds: serverFormData.timeoutSeconds,
      }
    };
    
    await updateAssistant({
      attId: assistantData.value.attId,
      attCompliancePlan: JSON.stringify(compliancePlan),
    });
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.saveSuccess'));
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.saveFailed'));
  }
};

// 重置函数
const handleBasicReset = () => {
  if (assistantData.value) {
    basicFormData.attName = assistantData.value.attName || '';
    basicFormData.attStatus = assistantData.value.attStatus || 1;
  }
};

const handleVoiceReset = async () => {
  if (assistantData.value && assistantData.value.attVoiceConfig) {
    try {
      const voiceData = JSON.parse(assistantData.value.attVoiceConfig);
      voiceFormData.provider = '11labs'; // 固定为 11Labs
      voiceFormData.voiceId = voiceData.voiceId || '';
      voiceFormData.model = voiceData.model || ''; // 只有11Labs才有这个字段
      voiceFormData.stability = voiceData.stability || 0.5;
      voiceFormData.similarityBoost = voiceData.similarityBoost || 0.75;
      
      // 更新选中的 Voice 名称
      if (voiceFormData.voiceId) {
        await loadVoiceList();
        const selectedVoice = voiceList.value.find((v: any) => v.diyCode === voiceFormData.voiceId);
        // 如果找不到匹配的 voice，显示 voiceId 本身
        selectedVoiceName.value = selectedVoice ? selectedVoice.diyName : voiceFormData.voiceId;
      }
    } catch (error) {
      console.warn('Failed to reset voice config:', error);
    }
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
      
      // 从后端返回的分离字段重置 System Prompt
      modelFormData.systemMessage = assistantData.value.adminSystemPrompt || '';
      modelFormData.userSystemMessage = assistantData.value.userSystemPrompt || '';
    } catch (error) {
      console.warn('Failed to reset model config:', error);
    }
  }
};

const handleTranscriberReset = () => {
  if (assistantData.value && assistantData.value.attTranscriberConfig) {
    try {
      const transcriberData = JSON.parse(assistantData.value.attTranscriberConfig);
      transcriberFormData.provider = transcriberData.provider || '';
      transcriberFormData.model = transcriberData.model || '';
      transcriberFormData.language = transcriberData.language || 'en';
    } catch (error) {
      console.warn('Failed to reset transcriber config:', error);
    }
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

const handleServerReset = () => {
  if (assistantData.value && assistantData.value.attCompliancePlan) {
    try {
      const complianceData = JSON.parse(assistantData.value.attCompliancePlan);
      if (complianceData.server) {
        serverFormData.url = complianceData.server.url || '';
        serverFormData.timeoutSeconds = complianceData.server.timeoutSeconds || 20;
      } else {
        serverFormData.url = '';
        serverFormData.timeoutSeconds = 20;
      }
    } catch (error) {
      console.warn('Failed to reset server config:', error);
      serverFormData.url = '';
      serverFormData.timeoutSeconds = 20;
    }
  } else {
    serverFormData.url = '';
    serverFormData.timeoutSeconds = 20;
  }
};

// Voice 选择弹窗相关函数
const openVoiceDialog = async () => {
  // 先加载 Voice 列表
  await loadVoiceList();
  
  // 检查当前 voiceId 是否在字典表中
  if (voiceFormData.voiceId) {
    const existsInDict = voiceList.value.some((v: any) => v.diyCode === voiceFormData.voiceId);
    
    // 如果不存在，提示用户是否要新建
    if (!existsInDict) {
      const dialog = DialogPlugin.confirm({
        header: t('pages.aiVoice.admin.assistantList.voiceNotExists'),
        body: t('pages.aiVoice.admin.assistantList.voiceNotExistsMessage').replace('{voiceId}', voiceFormData.voiceId),
        confirmBtn: t('pages.aiVoice.admin.assistantList.create'),
        cancelBtn: t('pages.aiVoice.admin.assistantList.cancel'),
        onConfirm: () => {
          // 打开新建弹窗，并填充编码
          voiceFormDataDialog.diyId = null;
          voiceFormDataDialog.diyName = '';
          voiceFormDataDialog.diyCode = voiceFormData.voiceId; // 填充当前 voiceId
          voiceFormDataDialog.diyDesc = '';
          voiceFormDataDialog.diyStatus = 1;
          voiceFormDialogVisible.value = true;
          dialog.destroy();
        },
        onCancel: () => {
          // 取消时仍然打开选择弹窗，让用户可以选择其他 voice
          voiceDialogVisible.value = true;
          dialog.destroy();
        },
      });
      return;
    }
  }
  
  // 如果存在或没有 voiceId，直接打开选择弹窗
  voiceDialogVisible.value = true;
};

const loadVoiceList = async () => {
  voiceListLoading.value = true;
  try {
    const res: any = await dictionaryService.getVoices();
    voiceList.value = res || [];
  } catch (e) {
    console.error(e);
    MessagePlugin.error('加载 Voice 列表失败');
  } finally {
    voiceListLoading.value = false;
  }
};

const handleSelectVoice = (row: any) => {
  voiceFormData.voiceId = row.diyCode;
  selectedVoiceName.value = row.diyName;
  voiceDialogVisible.value = false;
};

const handleCreateVoice = () => {
  voiceFormDataDialog.diyId = null;
  voiceFormDataDialog.diyName = '';
  voiceFormDataDialog.diyCode = '';
  voiceFormDataDialog.diyDesc = '';
  voiceFormDataDialog.diyStatus = 1;
  voiceFormDialogVisible.value = true;
};

const handleEditVoice = (row: any) => {
  voiceFormDataDialog.diyId = row.diyId;
  voiceFormDataDialog.diyName = row.diyName;
  voiceFormDataDialog.diyCode = row.diyCode;
  voiceFormDataDialog.diyDesc = row.diyDesc || '';
  voiceFormDataDialog.diyStatus = row.diyStatus;
  voiceFormDialogVisible.value = true;
};

const handleDeleteVoice = async (row: any) => {
  try {
    await dictionaryService.delete(row.diyId);
    MessagePlugin.success('删除成功');
    await loadVoiceList();
  } catch (e) {
    console.error(e);
    MessagePlugin.error('删除失败');
  }
};

const handleVoiceFormSubmit = async () => {
  try {
    if (voiceFormDataDialog.diyId) {
      await dictionaryService.update({
        diyId: voiceFormDataDialog.diyId,
        diyParentCode: 'VOICE',
        diyName: voiceFormDataDialog.diyName,
        diyCode: voiceFormDataDialog.diyCode,
        diyDesc: voiceFormDataDialog.diyDesc,
        diyStatus: voiceFormDataDialog.diyStatus,
      });
      MessagePlugin.success('更新成功');
    } else {
      await dictionaryService.create({
        diyParentCode: 'VOICE',
        diyName: voiceFormDataDialog.diyName,
        diyCode: voiceFormDataDialog.diyCode,
        diyDesc: voiceFormDataDialog.diyDesc,
        diyStatus: voiceFormDataDialog.diyStatus,
      });
      MessagePlugin.success('创建成功');
    }
    voiceFormDialogVisible.value = false;
    await loadVoiceList();
  } catch (e) {
    console.error(e);
    MessagePlugin.error('操作失败');
  }
};

const handleModelProviderChange = () => {
  modelFormData.model = '';
};

// 更新助手的通用函数
const updateAssistant = async (params: Record<string, unknown>) => {
  await adminAssistantService.updateAssistant(params);
  // 重新加载数据
  await loadAssistantDetail();
};

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-';
  return new Date(dateTime).toLocaleString();
};

onMounted(() => {
  loadAssistantDetail();
});
</script>

<style scoped lang="less">
.assistant-detail {
  padding: 24px;

  .loading-container {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 200px;
  }

  .detail-content {
    .settings-content {
      padding: 24px 0;
    }

    .assigned-user-section {
      h4 {
        margin-bottom: 16px;
        color: var(--td-text-color-primary);
        font-size: 16px;
        font-weight: 600;
      }
    }

    .assigned-user-card {
      border: 1px solid var(--td-border-level-1-color);
      border-radius: var(--td-radius-default);
      padding: 16px;
      background: var(--td-bg-color-container);

      .user-info {
        display: flex;
        align-items: center;
        gap: 16px;

        .user-details {
          flex: 1;

          .user-name {
            font-size: 16px;
            font-weight: 500;
            color: var(--td-text-color-primary);
            margin-bottom: 4px;
          }

          .user-account {
            font-size: 14px;
            color: var(--td-text-color-secondary);
            margin-bottom: 2px;
          }

          .user-mobile {
            font-size: 12px;
            color: var(--td-text-color-placeholder);
          }
        }

        .user-actions {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
      }

      .no-user {
        text-align: center;
        padding: 20px;

        .no-user-text {
          margin-bottom: 16px;
          color: var(--td-text-color-placeholder);
        }
      }
    }

    .system-prompt-section {
      margin-top: 24px;
      
      h4 {
        margin-bottom: 16px;
        color: var(--td-text-color-primary);
        font-size: 16px;
        font-weight: 600;
      }

      .prompt-container {
        border: 1px solid var(--td-border-level-1-color);
        border-radius: var(--td-radius-default);
        padding: 16px;
        background: var(--td-bg-color-container);
      }
    }

    .artifact-plan-section,
    .server-config-section {
      margin-top: 24px;
      
      h4 {
        margin-bottom: 16px;
        color: var(--td-text-color-primary);
        font-size: 16px;
        font-weight: 600;
      }
    }

    .message-content {
      max-width: 100%;
      word-break: break-word;
      white-space: pre-wrap;
    }

    .url-text {
      word-break: break-all;
    }

    .tool-tag,
    .file-tag,
    .server-message-tag,
    .output-id-tag,
    .scorecard-id-tag {
      margin-right: 8px;
      margin-bottom: 4px;
    }

    .slider-value {
      text-align: center;
      margin-top: 8px;
      font-weight: 500;
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

    .timeout-unit {
      margin-left: 8px;
      color: var(--td-text-color-placeholder);
      font-size: 14px;
    }

    .search-actions-right {
      display: flex;
      justify-content: flex-end;
      width: 100%;
    }

    .user-search-form {
      margin-bottom: 16px;
      width: 100%;
    }

    .user-search-form :deep(.t-form) {
      width: 100%;
    }

    .user-search-row {
      display: flex;
      align-items: flex-end;
      gap: 16px;
      flex-wrap: nowrap;
      width: 100%;
    }

    .user-search-item {
      flex: 1;
      margin-bottom: 0;
      min-width: 0;
    }

    .user-search-item :deep(.t-form-item) {
      margin-bottom: 0;
    }

    .user-search-item :deep(.t-form-item__label) {
      width: auto;
      min-width: 80px;
    }

    .user-search-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      margin-left: auto;
      padding-bottom: 4px;
      flex-shrink: 0;
    }

    .user-list-container {
      position: relative;
      min-height: 300px;
      margin-top: 16px;
    }

    .top-items-hint {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      padding: 8px 16px;
      font-size: 12px;
      color: var(--td-text-color-placeholder);
      background: var(--td-bg-color-container);
      border-top: 1px solid var(--td-border-level-1-color);
      z-index: 10;
    }
  }
}

:deep(.user-search-actions) {
  display: flex;
  justify-content: flex-end;
  margin-left: auto;
  flex-shrink: 0;
}
</style>
