import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const push = vi.fn();
const listCustomerServices = vi.fn();
const deleteCustomerService = vi.fn();
const restoreCustomerService = vi.fn();
const purgeCustomerService = vi.fn();
const importIndustryDemosMock = vi.fn();
let loadFails = false;

vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }));
vi.mock('@/api/platform', () => ({
  RealtimeVoiceService: class {
    listCustomerServices(...args: unknown[]) {
      if (loadFails) return Promise.reject(new Error('load failed'));
      return listCustomerServices(...args);
    }
    deleteCustomerService(...args: unknown[]) {
      return deleteCustomerService(...args);
    }
    restoreCustomerService(...args: unknown[]) {
      return restoreCustomerService(...args);
    }
    purgeCustomerService(...args: unknown[]) {
      return purgeCustomerService(...args);
    }
    importIndustryDemos(...args: unknown[]) {
      return importIndustryDemosMock(...args);
    }
  },
}));

import InstanceListPage from './index.vue';

const activeItem = {
  id: '00000000-0000-0000-0000-000000000102',
  display_name: '新北语音前台',
  organization_name: '新北门店',
  business_profile: 'generic-receptionist',
  primary_language: 'zh-CN',
  version: 3,
  deleted_at: null as string | null,
};

const deletedItem = {
  ...activeItem,
  id: '00000000-0000-0000-0000-000000000103',
  display_name: '已删前台',
  deleted_at: '2026-08-17T01:00:00Z',
};

describe('tenant instance list', () => {
  beforeEach(() => {
    loadFails = false;
    push.mockClear();
    listCustomerServices.mockReset();
    deleteCustomerService.mockReset().mockResolvedValue(undefined);
    restoreCustomerService.mockReset().mockResolvedValue(activeItem);
    purgeCustomerService.mockReset().mockResolvedValue(undefined);
    importIndustryDemosMock.mockReset().mockResolvedValue({ created: 7, skipped: 0 });
    listCustomerServices.mockResolvedValue({
      total: 1,
      items: [activeItem],
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('renders PostgreSQL-backed UUID instances and selects one', async () => {
    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('新北语音前台');
    expect(wrapper.text()).toContain('新北门店');
    await wrapper.get('.row-main').trigger('click');
    expect(push).toHaveBeenCalledWith({
      name: 'KnowledgeBaseIndex',
      query: { instanceId: '00000000-0000-0000-0000-000000000102' },
    });
  });

  it('opens realtime voice with the selected instance', async () => {
    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();

    await wrapper.get('[data-testid="start-voice-button"]').trigger('click');
    expect(push).toHaveBeenCalledWith({
      name: 'UserRealtimeVoiceIndex',
      query: { instanceId: '00000000-0000-0000-0000-000000000102' },
    });
  });

  it('imports industry demo instances and reloads the list', async () => {
    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();

    await wrapper.get('[data-testid="import-industry"]').trigger('click');
    await flushPromises();

    expect(importIndustryDemosMock).toHaveBeenCalled();
    expect(listCustomerServices.mock.calls.length).toBeGreaterThan(1);
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

  it('soft-deletes and restores from the deleted view', async () => {
    listCustomerServices
      .mockResolvedValueOnce({ total: 1, items: [activeItem] })
      .mockResolvedValueOnce({ total: 0, items: [] })
      .mockResolvedValueOnce({ total: 1, items: [deletedItem] })
      .mockResolvedValueOnce({ total: 1, items: [activeItem] });

    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();

    await wrapper.get('[data-testid="soft-delete-button"]').trigger('click');
    await flushPromises();
    expect(deleteCustomerService).toHaveBeenCalledWith(activeItem.id);

    await wrapper.get('[data-testid="show-deleted"]').setValue(true);
    await flushPromises();
    expect(listCustomerServices).toHaveBeenCalledWith(
      expect.objectContaining({ includeDeleted: true }),
    );
    expect(wrapper.text()).toContain('已删前台');

    await wrapper.get('[data-testid="restore-button"]').trigger('click');
    await flushPromises();
    expect(restoreCustomerService).toHaveBeenCalledWith(deletedItem.id);
  });

  it('purges a soft-deleted instance', async () => {
    listCustomerServices.mockImplementation((page: { includeDeleted?: boolean } = {}) => {
      if (page.includeDeleted) {
        return Promise.resolve({ total: 1, items: [deletedItem] });
      }
      return Promise.resolve({ total: 0, items: [] });
    });

    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();
    await wrapper.get('[data-testid="show-deleted"]').setValue(true);
    await flushPromises();

    listCustomerServices.mockImplementation(() => Promise.resolve({ total: 0, items: [] }));
    await wrapper.get('[data-testid="purge-button"]').trigger('click');
    await flushPromises();
    expect(purgeCustomerService).toHaveBeenCalledWith(deletedItem.id);
  });

  it('surfaces purge conflict when call records remain', async () => {
    listCustomerServices.mockImplementation((page: { includeDeleted?: boolean } = {}) => {
      if (page.includeDeleted) {
        return Promise.resolve({ total: 1, items: [deletedItem] });
      }
      return Promise.resolve({ total: 0, items: [] });
    });
    purgeCustomerService.mockRejectedValueOnce(
      new Error('该实例下仍有通话记录，无法完全删除'),
    );
    const wrapper = mount(InstanceListPage, {
      global: { stubs: { 't-tag': true } },
    });
    await flushPromises();
    await wrapper.get('[data-testid="show-deleted"]').setValue(true);
    await flushPromises();

    await wrapper.get('[data-testid="purge-button"]').trigger('click');
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('仍有通话记录');
  });
});
