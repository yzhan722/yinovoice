import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/api/platform', () => ({
  CUSTOMER_SERVICE_VERSION_CONFLICT: '配置已被更新，请刷新后重试',
  DEMO_CUSTOMER_SERVICE_ID: '00000000-0000-0000-0000-000000000101',
  TTS_VOICE_OPTIONS: [
    { value: 'longanqian', label: '龙安仟（沉稳女声）' },
    { value: 'longanhuan_v3.6', label: '龙安欢' },
  ],
  TenantAppointmentService: class {
    list() {
      return Promise.resolve({ list: [] });
    }
  },
  TenantKnowledgeService: class {
    getList() {
      return Promise.resolve({ records: [] });
    }
  },
  TenantCallbackService: class {
    list() {
      return Promise.resolve({
        list: [{
          id: 'callback-1',
          callerPhone: '13800000000',
          reason: 'fake phone callback',
          status: 'open',
        }],
      });
    }
  },
  RealtimeVoiceService: class {
    listCustomerServices() {
      return Promise.resolve({
        items: [{ id: '00000000-0000-0000-0000-000000000101' }],
        total: 1,
      });
    }
    getCustomerService() {
      return Promise.resolve({
        id: '00000000-0000-0000-0000-000000000101',
        tenant_id: '00000000-0000-0000-0000-000000000001',
        version: 1,
        display_name: 'demo',
        organization_name: 'demo org',
        business_profile: 'generic-receptionist',
        primary_language: 'zh-CN',
        greeting: '您好',
        platform_prompt: '演示平台 Prompt',
        tenant_prompt: '演示业务 Prompt',
        voice: {
          preset_id: 'mandarin-standard',
          locale: 'zh-CN',
          speaking_rate: 1,
          volume: 1,
          pitch: 0,
          style: 'professional-friendly',
          emotion: 'neutral',
          pause_profile: 'receptionist',
          tts_voice: 'longanqian',
        },
        response: {
          brevity: 'concise',
          max_spoken_sentences: 3,
          ask_one_question_at_a_time: true,
        },
      });
    }
    updateCustomerService() {
      return Promise.resolve({});
    }
  },
}));

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }));
vi.mock('@/api/platform/instanceSelection', () => ({
  loadStoredInstanceId: (): string | null => null,
  resolveInstanceSelection: ({ availableIds }: { availableIds: string[] }): string | null =>
    availableIds[0] || null,
  storeInstanceId: (_instanceId: string | null): void => {},
}));

import AppointmentsPage from './appointments/index.vue';
import CallbackTasksPage from './callback-tasks/index.vue';
import KnowledgeBasePage from './knowledge-base/index.vue';

describe('planned tenant modules remain truthful', () => {
  it('labels appointments as an unconnected demonstration framework', async () => {
    const wrapper = mount(AppointmentsPage);
    await flushPromises();

    expect(wrapper.text()).toContain('规划中 · 演示框架');
    expect(wrapper.text()).toContain('尚未接通实时语音或电话流程');
  });

  it('labels knowledge base files as unconnected and exposes business prompt editor', async () => {
    const wrapper = mount(KnowledgeBasePage, {
      global: {
        stubs: {
          't-button': true,
          't-table': true,
          't-dialog': true,
          't-upload': true,
          't-tag': true,
          't-textarea': true,
          't-select': true,
        },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('可切换客服音色');
    expect(wrapper.text()).toContain('底层对话逻辑由平台管理');
    expect(wrapper.text()).toContain('尚未接入实时语音检索增强');
    expect(wrapper.text()).toContain('业务知识 Prompt');
    expect(wrapper.text()).toContain('底层逻辑 Prompt（只读）');
    expect(wrapper.text()).toContain('客服音色');
  });

  it('labels callback telephony as a non-operational demonstration framework', async () => {
    const wrapper = mount(CallbackTasksPage, {
      global: {
        stubs: {
          't-drawer': true,
          't-descriptions': true,
          't-descriptions-item': true,
        },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('规划中 · 演示框架');
    expect(wrapper.text()).toContain('电话业务尚未接通');
    expect(wrapper.text()).not.toContain('13800000000');
    expect(wrapper.findAll('button').map((button) => button.text())).not.toContain('完成');
    expect(wrapper.findAll('button').map((button) => button.text())).not.toContain('重开');
  });
});
