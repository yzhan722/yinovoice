import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

const createCustomerService = vi.fn();
vi.mock('@/api/platform', () => ({
  RealtimeVoiceService: class {
    createCustomerService = createCustomerService;
  },
  TTS_VOICE_OPTIONS: [{ value: 'longanqian', label: 'Demo voice' }],
}));

import InstanceCreateDialog from './InstanceCreateDialog.vue';

describe('InstanceCreateDialog', () => {
  it('opens with non-empty synthetic defaults', () => {
    const wrapper = mount(InstanceCreateDialog);
    expect((wrapper.get('[data-testid="display-name"]').element as HTMLInputElement).value).not.toBe('');
    expect((wrapper.get('[data-testid="organization-name"]').element as HTMLInputElement).value).not.toBe('');
    expect((wrapper.get('[data-testid="greeting"]').element as HTMLTextAreaElement).value).not.toBe('');
    const textareas = wrapper.findAll('textarea');
    expect(textareas.length).toBeGreaterThanOrEqual(3);
    expect((textareas[1].element as HTMLTextAreaElement).value.length).toBeGreaterThan(20);
    expect((textareas[2].element as HTMLTextAreaElement).value.length).toBeGreaterThan(20);
  });

  it('submits safe defaults and emits the created instance', async () => {
    const created = { id: '00000000-0000-0000-0000-000000000201' };
    createCustomerService.mockResolvedValueOnce(created);
    const wrapper = mount(InstanceCreateDialog);

    await wrapper.get('[data-testid="display-name"]').setValue('Synthetic Support');
    await wrapper.get('[data-testid="organization-name"]').setValue('Demo Organization');
    await wrapper.get('[data-testid="greeting"]').setValue('Hello, how may I help you?');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(createCustomerService).toHaveBeenCalledWith(expect.objectContaining({
      display_name: 'Synthetic Support',
      organization_name: 'Demo Organization',
      greeting: 'Hello, how may I help you?',
      platform_prompt: expect.stringContaining('Yino'),
      tenant_prompt: expect.stringContaining('合成演示机构'),
      voice: expect.objectContaining({ tts_voice: 'longanqian' }),
      response: expect.objectContaining({ ask_one_question_at_a_time: true }),
    }));
    expect(wrapper.emitted('created')?.[0]).toEqual([created]);
  });

  it('keeps entered values and shows an error when creation fails', async () => {
    createCustomerService.mockRejectedValueOnce(new Error('safe failure'));
    const wrapper = mount(InstanceCreateDialog);
    const name = wrapper.get('[data-testid="display-name"]');
    await name.setValue('Keep this value');
    await wrapper.get('[data-testid="organization-name"]').setValue('Demo Organization');
    await wrapper.get('[data-testid="greeting"]').setValue('Hello there');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect((name.element as HTMLInputElement).value).toBe('Keep this value');
    expect(wrapper.get('[role="alert"]').text()).toContain('创建失败');
    expect(wrapper.emitted('created')).toBeUndefined();
  });
});
