import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const push = vi.fn();
let loadFails = false;
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }));
vi.mock('@/api/platform', () => ({
  RealtimeVoiceService: class {
    listCustomerServices() {
      if (loadFails) return Promise.reject(new Error('load failed'));
      return Promise.resolve({
        total: 1,
        items: [{
          id: '00000000-0000-0000-0000-000000000102',
          display_name: '新北语音前台',
          organization_name: '新北门店',
          business_profile: 'generic-receptionist',
          primary_language: 'zh-CN',
          version: 3,
        }],
      });
    }
  },
}));

import InstanceListPage from './index.vue';

describe('tenant instance list', () => {
  beforeEach(() => {
    loadFails = false;
    push.mockClear();
  });

  it('renders PostgreSQL-backed UUID instances and selects one', async () => {
    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('新北语音前台');
    expect(wrapper.text()).toContain('新北门店');
    await wrapper.get('button.row').trigger('click');
    expect(push).toHaveBeenCalledWith({
      name: 'KnowledgeBaseIndex',
      query: { instanceId: '00000000-0000-0000-0000-000000000102' },
    });
  });

  it('opens creation and routes to a newly created UUID', async () => {
    const wrapper = mount(InstanceListPage, {
      global: {
        stubs: {
          't-tag': true,
          InstanceCreateDialog: {
            template: '<button data-testid="finish-create" @click="$emit(\'created\', { id: \'00000000-0000-0000-0000-000000000202\' })">finish</button>',
          },
        },
      },
    });
    await flushPromises();
    await wrapper.get('[data-testid="new-instance"]').trigger('click');
    await wrapper.get('[data-testid="finish-create"]').trigger('click');

    expect(push).toHaveBeenCalledWith({
      name: 'KnowledgeBaseIndex',
      query: { instanceId: '00000000-0000-0000-0000-000000000202' },
    });
  });

  it('shows a load error instead of an empty list', async () => {
    loadFails = true;
    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain('加载失败');
    expect(wrapper.text()).not.toContain('暂无实例');
  });
});
