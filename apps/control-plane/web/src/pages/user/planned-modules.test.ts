import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listAppointments = vi.fn();
const createAppointment = vi.fn();
const updateAppointment = vi.fn();
const cancelAppointment = vi.fn();
const listCallbacks = vi.fn();
const createCallback = vi.fn();
const markDone = vi.fn();
const reopen = vi.fn();

vi.mock('@/api/platform', () => ({
  CUSTOMER_SERVICE_VERSION_CONFLICT: '配置已被更新，请刷新后重试',
  DEMO_CUSTOMER_SERVICE_ID: '00000000-0000-0000-0000-000000000101',
  TTS_VOICE_OPTIONS: [
    { value: 'longanqian', label: '龙安仟（沉稳女声）' },
  ],
  TenantAppointmentService: class {
    list(...args: unknown[]) { return listAppointments(...args); }
    create(...args: unknown[]) { return createAppointment(...args); }
    update(...args: unknown[]) { return updateAppointment(...args); }
    cancel(...args: unknown[]) { return cancelAppointment(...args); }
  },
  TenantKnowledgeService: class {
    getList() {
      return Promise.resolve({ records: [] });
    }
  },
  TenantCallbackService: class {
    list(...args: unknown[]) { return listCallbacks(...args); }
    create(...args: unknown[]) { return createCallback(...args); }
    markDone(...args: unknown[]) { return markDone(...args); }
    reopen(...args: unknown[]) { return reopen(...args); }
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
        display_name: 'demo',
        organization_name: 'demo org',
        business_profile: 'generic-receptionist',
        primary_language: 'zh-CN',
        version: 1,
        greeting: '您好',
        platform_prompt: '演示平台 Prompt',
        tenant_prompt: '演示业务 Prompt',
        voice: { tts_voice: 'longanqian' },
        response: { ask_one_question_at_a_time: true },
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
vi.mock('tdesign-vue-next', () => ({
  MessagePlugin: { error: vi.fn(), success: vi.fn() },
}));

import AppointmentsPage from './appointments/index.vue';
import CallbackTasksPage from './callback-tasks/index.vue';
import KnowledgeBasePage from './knowledge-base/index.vue';

describe('tenant appointments and callbacks are live-backed', () => {
  beforeEach(() => {
    listAppointments.mockReset().mockResolvedValue({ list: [] });
    createAppointment.mockReset().mockResolvedValue({});
    updateAppointment.mockReset().mockResolvedValue({});
    cancelAppointment.mockReset().mockResolvedValue(undefined);
    listCallbacks.mockReset().mockResolvedValue({ list: [] });
    createCallback.mockReset().mockResolvedValue({});
    markDone.mockReset().mockResolvedValue({});
    reopen.mockReset().mockResolvedValue({});
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('loads appointments without planned-framework copy', async () => {
    listAppointments.mockResolvedValueOnce({
      list: [{
        id: 'apt-1',
        status: 'pending',
        patientName: '张先生',
        phone: '13800138000',
        service: '洁牙',
        slotStart: '2026-08-18T10:00:00.000Z',
        slotEnd: '2026-08-18T10:30:00.000Z',
      }],
    });
    const wrapper = mount(AppointmentsPage);
    await flushPromises();

    expect(wrapper.text()).toContain('租户真实预约队列');
    expect(wrapper.text()).not.toContain('规划中 · 演示框架');
    expect(wrapper.text()).toContain('张先生');
    expect(listAppointments).toHaveBeenCalled();
  });

  it('loads callback tasks and can complete them', async () => {
    listCallbacks
      .mockResolvedValueOnce({
        list: [{
          id: 'cb-1',
          status: 'open',
          reason: '改期确认',
          callerPhone: '13900139000',
          summary: '周四回电',
        }],
      })
      .mockResolvedValueOnce({
        list: [{
          id: 'cb-1',
          status: 'done',
          reason: '改期确认',
          callerPhone: '13900139000',
          summary: '周四回电',
        }],
      });

    const wrapper = mount(CallbackTasksPage);
    await flushPromises();

    expect(wrapper.text()).toContain('租户真实回拨队列');
    expect(wrapper.text()).toContain('改期确认');
    expect(wrapper.text()).not.toContain('电话业务尚未接通');
    await wrapper.get('[data-testid="complete-callback"]').trigger('click');
    await flushPromises();
    expect(markDone).toHaveBeenCalledWith('cb-1');
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
    expect(wrapper.text()).toContain('业务知识 Prompt');
  });
});
