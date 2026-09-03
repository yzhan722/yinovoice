import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent } from 'vue';

import { INSTANCE_SELECTION_STORAGE_KEY } from '@/api/platform/instanceSelection';
import type { CustomerServiceInstance, TtsVoiceId } from '@/api/platform/RealtimeVoiceService';

const listCustomerServices = vi.fn();
const updateCustomerService = vi.fn();
const replace = vi.fn();

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace }),
}));
vi.mock('@/api/platform/RealtimeVoiceService', async () => {
  const actual = await vi.importActual<typeof import('@/api/platform/RealtimeVoiceService')>(
    '@/api/platform/RealtimeVoiceService',
  );
  return {
    ...actual,
    RealtimeVoiceService: class {
      listCustomerServices(...args: unknown[]) {
        return listCustomerServices(...args);
      }
      updateCustomerService(...args: unknown[]) {
        return updateCustomerService(...args);
      }
    },
  };
});

import RealtimeVoicePage from './index.vue';

const firstId = '00000000-0000-0000-0000-000000000102';
const secondId = '00000000-0000-0000-0000-000000000202';

function instance(overrides: Partial<CustomerServiceInstance> = {}): CustomerServiceInstance {
  return {
    id: firstId,
    tenant_id: '00000000-0000-0000-0000-000000000001',
    version: 3,
    display_name: '新北前台',
    organization_name: '新北门店',
    business_profile: 'generic-receptionist',
    primary_language: 'zh-CN',
    greeting: '您好，请问有什么可以帮您？',
    platform_prompt: '平台规则',
    tenant_prompt: '业务知识',
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
    ...overrides,
  };
}

const firstInstance = instance();
const secondInstance = instance({
  id: secondId,
  display_name: '城西前台',
  organization_name: '城西诊所',
  voice: { ...instance().voice, tts_voice: 'longanfengyue' },
});

const PanelStub = defineComponent({
  name: 'LiveKitRealtimePanel',
  props: {
    customerServiceId: {
      type: String,
      required: true,
    },
  },
  template: '<div data-testid="panel-service">{{ customerServiceId }}</div>',
});

function mountPage() {
  return mount(RealtimeVoicePage, {
    global: {
      stubs: {
        LiveKitRealtimePanel: PanelStub,
      },
    },
  });
}

describe('tenant realtime voice page', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    replace.mockReset();
    listCustomerServices.mockReset().mockResolvedValue({
      items: [firstInstance],
      total: 1,
    });
    updateCustomerService.mockReset().mockImplementation(
      (_id: string, update: { voice: { tts_voice: TtsVoiceId }; expected_version: number }) =>
        Promise.resolve(instance({
          version: update.expected_version + 1,
          voice: { ...firstInstance.voice, tts_voice: update.voice.tts_voice },
        })),
    );
  });

  it('mounts the continuous LiveKit panel with the selected tenant instance', async () => {
    const wrapper = mountPage();
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="panel-service"]').exists()).toBe(true);
    });

    expect(wrapper.get('[data-testid="panel-service"]').text()).toBe(firstId);
    expect(wrapper.get('[data-testid="voice-instance-select"]').element).toHaveProperty(
      'value',
      firstId,
    );
    expect(wrapper.get('[data-testid="voice-tts-select"]').element).toHaveProperty(
      'value',
      'longanqian',
    );
    expect(wrapper.text()).toContain('切换实例或音色会结束当前通话');
    expect(wrapper.text()).not.toContain('本地 Demo');
    expect(window.sessionStorage.getItem(INSTANCE_SELECTION_STORAGE_KEY)).toBe(firstId);
  });

  it('switches the LiveKit panel to another tenant voice instance', async () => {
    listCustomerServices.mockResolvedValue({
      items: [firstInstance, secondInstance],
      total: 2,
    });
    const wrapper = mountPage();
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="panel-service"]').exists()).toBe(true);
    });

    expect(wrapper.get('[data-testid="panel-service"]').text()).toBe(firstId);
    const select = wrapper.get('[data-testid="voice-instance-select"]');
    expect(select.text()).toContain('新北前台');
    expect(select.text()).toContain('城西前台');

    await select.setValue(secondId);
    await flushPromises();

    expect(wrapper.get('[data-testid="panel-service"]').text()).toBe(secondId);
    expect(wrapper.get('[data-testid="voice-tts-select"]').element).toHaveProperty(
      'value',
      'longanfengyue',
    );
    expect(window.sessionStorage.getItem(INSTANCE_SELECTION_STORAGE_KEY)).toBe(secondId);
    expect(replace).toHaveBeenCalledWith({
      query: { instanceId: secondId },
    });
  });

  it('saves a selected TTS voice onto the current instance', async () => {
    const wrapper = mountPage();
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="voice-tts-select"]').exists()).toBe(true);
    });

    await wrapper.get('[data-testid="voice-tts-select"]').setValue('longchuanshu_v3.6');
    await flushPromises();

    expect(updateCustomerService).toHaveBeenCalledWith(
      firstId,
      expect.objectContaining({
        expected_version: 3,
        voice: expect.objectContaining({ tts_voice: 'longchuanshu_v3.6' }),
      }),
    );
    expect(wrapper.get('[data-testid="voice-tts-select"]').element).toHaveProperty(
      'value',
      'longchuanshu_v3.6',
    );
  });
});
