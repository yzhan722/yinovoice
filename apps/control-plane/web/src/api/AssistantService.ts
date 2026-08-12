// Mock data service for Assistant Management
export class AssistantService {
  /**
   * Get assistant list with pagination
   */
  getAssistantList(params: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const { current = 1, pageSize = 10 } = params;
        const mockAssistants = this.generateMockAssistants();
        const start = (current - 1) * pageSize;
        const end = start + pageSize;
        const list = mockAssistants.slice(start, end);
        
        resolve({
          list,
          total: mockAssistants.length,
          current,
          pageSize,
        });
      }, 300);
    });
  }

  /**
   * Get assistant detail by ID
   */
  getAssistantDetail(assistantId: string) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const assistant = this.generateMockAssistants().find(a => a.id === assistantId);
        if (assistant) {
          resolve({
            ...assistant,
            ...this.getFullAssistantConfig(),
          });
        } else {
          resolve(null);
        }
      }, 200);
    });
  }

  /**
   * Get current user's assistant (for user side)
   */
  getUserAssistant() {
    return new Promise((resolve) => {
      setTimeout(() => {
        const baseAssistant = this.generateMockAssistants()[0];
        const fullConfig = this.getFullAssistantConfig();
        resolve({
          ...baseAssistant,
          ...fullConfig,
        });
      }, 200);
    });
  }

  /**
   * Update assistant settings
   */
  updateAssistant(assistantId: string, data: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          success: true,
          assistantId,
          ...data,
        });
      }, 300);
    });
  }

  /**
   * Generate mock assistants data
   */
  private generateMockAssistants() {
    const names = ['Riley', 'Alex', 'Sam', 'Jordan', 'Taylor', 'Casey', 'Morgan', 'Cameron'];
    const voiceProviders = ['elevenlabs', 'azure', 'openai', 'deepgram'];
    const models = ['gpt-4', 'gpt-3.5-turbo', 'claude-3-opus', 'claude-3-sonnet'];
    const statuses = ['active', 'inactive'];
    
    const assistants = [];
    const now = new Date();
    
    for (let i = 0; i < 20; i++) {
      const createdAt = new Date(now.getTime() - Math.random() * 180 * 24 * 60 * 60 * 1000);
      const name = names[Math.floor(Math.random() * names.length)];
      const userId = `user_${Math.floor(Math.random() * 10) + 1}`;
      const userName = `User ${Math.floor(Math.random() * 10) + 1}`;
      
      assistants.push({
        id: `assistant_${i + 1}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        orgId: 'org_123456',
        createdAt: createdAt.toISOString(),
        updatedAt: new Date().toISOString(),
        assistantId: `assistant_${i + 1}`,
        assistantName: name,
        name: name,
        userId,
        userName,
        voiceProvider: voiceProviders[Math.floor(Math.random() * voiceProviders.length)],
        model: models[Math.floor(Math.random() * models.length)],
        status: statuses[Math.floor(Math.random() * statuses.length)],
        createTime: createdAt.toISOString(),
      });
    }
    
    return assistants.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }

  /**
   * Get full assistant configuration - matches API documentation structure
   */
  private getFullAssistantConfig() {
    return {
      id: 'assistant_1',
      orgId: 'org_123456',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      name: 'Riley',
      model: {
        provider: 'openai',
        model: 'gpt-4',
        temperature: 0.7,
        maxTokens: 2000,
        messages: [
          {
            role: 'system',
            content: 'You are a helpful customer service assistant. Be friendly, professional, and aim to resolve customer inquiries efficiently.',
          },
        ],
      },
      voice: {
        provider: 'elevenlabs',
        voiceId: '21m00Tcm4TlvDq8ikWAM',
        cachingEnabled: true,
        speed: 1.0,
      },
      transcriber: {
        provider: 'deepgram',
        language: 'en',
        model: 'nova-2',
        confidenceThreshold: 0.4,
        backgroundDenoisingEnabled: false,
        useNumerals: false,
        //@ts-ignore
        keyterms: [],
      },
      firstMessage: 'Hello! How can I help you today?',
      firstMessageMode: 'assistant-speaks-first',
      maxDurationSeconds: 600,
      analysisPlan: {
        minMessagesThreshold: 2,
        summaryPlan: {
          enabled: true,
          prompt: 'You are an expert note-taker. You will be given a transcript of a call. Summarize the call in 2-3 sentences, if applicable.',
          timeoutSeconds: 10,
        },
        successEvaluationPlan: {
          enabled: true,
          rubric: 'NumericScale',
          prompt: '',
          timeoutSeconds: 10,
        },
      },
      artifactPlan: {
        recordingEnabled: true,
        recordingFormat: 'wav',
        transcriptPlan: {
          enabled: true,
          assistantName: 'Assistant',
          userName: 'User',
        },
        loggingEnabled: true,
      },
      compliancePlan: {
        hipaaEnabled: {
          hipaaEnabled: false,
        },
        pciEnabled: {
          pciEnabled: false,
        },
      },
    };
  }
}

