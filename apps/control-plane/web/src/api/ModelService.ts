// Mock data service for Model Settings
export class ModelService {
  /**
   * Get current model settings
   */
  getModelSettings() {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          provider: 'openai',
          modelName: 'gpt-4',
          apiKey: 'sk-***hidden***',
          temperature: 0.7,
          maxTokens: 2000,
          topP: 1.0,
          frequencyPenalty: 0,
          presencePenalty: 0,
          availableProviders: [
            { label: 'OpenAI', value: 'openai' },
            { label: 'Anthropic', value: 'anthropic' },
            { label: 'Google', value: 'google' },
          ],
          availableModels: {
            openai: [
              { label: 'gpt-4', value: 'gpt-4' },
              { label: 'gpt-4-turbo', value: 'gpt-4-turbo' },
              { label: 'gpt-3.5-turbo', value: 'gpt-3.5-turbo' },
            ],
            anthropic: [
              { label: 'claude-3-opus', value: 'claude-3-opus-20240229' },
              { label: 'claude-3-sonnet', value: 'claude-3-sonnet-20240229' },
              { label: 'claude-3-haiku', value: 'claude-3-haiku-20240307' },
            ],
            google: [
              { label: 'gemini-pro', value: 'gemini-pro' },
              { label: 'gemini-ultra', value: 'gemini-ultra' },
            ],
          },
        });
      }, 200);
    });
  }

  /**
   * Update model settings
   */
  updateModelSettings(data: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          success: true,
          ...data,
        });
      }, 300);
    });
  }
}

