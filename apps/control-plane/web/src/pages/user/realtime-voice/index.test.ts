import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { defineComponent } from 'vue';

import RealtimeVoicePage from './index.vue';

describe('tenant realtime voice page', () => {
  it('mounts the continuous LiveKit panel and states the Demo boundary truthfully', () => {
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

    expect(wrapper.text()).toContain(
      '本地网页实时语音 Demo；电话、预约、知识库尚未接通',
    );
    expect(wrapper.get('[data-testid="panel-service"]').text()).toBe(
      '00000000-0000-0000-0000-000000000101',
    );
    expect(wrapper.text()).not.toContain('电话已接通');
    expect(wrapper.text()).not.toContain('知识库已接通');
  });
});
