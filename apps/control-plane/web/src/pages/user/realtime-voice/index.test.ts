import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { defineComponent } from 'vue';

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }));
vi.mock('@/api/platform/RealtimeVoiceService', () => ({
  RealtimeVoiceService: class {
    listCustomerServices() {
      return Promise.resolve({
        items: [{ id: '00000000-0000-0000-0000-000000000102', display_name: '新北前台' }],
        total: 1,
      });
    }
  },
}));
vi.mock('@/api/platform/instanceSelection', () => ({
  loadStoredInstanceId: (): string | null => null,
  resolveInstanceSelection: ({ availableIds }: { availableIds: string[] }): string | null =>
    availableIds[0] || null,
  storeInstanceId: (_instanceId: string | null): void => {},
}));

import RealtimeVoicePage from './index.vue';

describe('tenant realtime voice page', () => {
  it('mounts the continuous LiveKit panel with the selected tenant instance', async () => {
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
    const wrapper = mount(RealtimeVoicePage, {
      global: {
        stubs: {
          LiveKitRealtimePanel: PanelStub,
        },
      },
    });
    await flushPromises();
    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="panel-service"]').exists()).toBe(true);
    });

    expect(wrapper.text()).toContain(
      '本地网页实时语音 Demo；电话、预约、知识库尚未接通',
    );
    expect(wrapper.get('[data-testid="panel-service"]').text()).toBe(
      '00000000-0000-0000-0000-000000000102',
    );
    expect(wrapper.text()).not.toContain('电话已接通');
    expect(wrapper.text()).not.toContain('知识库已接通');
  });
});
