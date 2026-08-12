// Mock data service for Call History
export class CallService {
  /**
   * Get call list with pagination
   */
  getCallList(params: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const { current = 1, pageSize = 10 } = params;
        const mockCalls = this.generateMockCalls();
        const start = (current - 1) * pageSize;
        const end = start + pageSize;
        const list = mockCalls.slice(start, end);
        
        resolve({
          list,
          total: mockCalls.length,
          current,
          pageSize,
        });
      }, 300);
    });
  }

  /**
   * Get call detail by ID
   */
  getCallDetail(callId: string) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const call = this.generateMockCalls().find(c => c.id === callId);
        if (call) {
          resolve({
            ...call,
            transcript: this.generateTranscript(),
            messages: this.generateMessages(),
          });
        } else {
          resolve(null);
        }
      }, 200);
    });
  }

  /**
   * Generate mock calls data
   */
  private generateMockCalls() {
    const types = ['inboundPhoneCall', 'outboundPhoneCall', 'webCall'];
    const statuses = ['queued', 'ringing', 'in-progress', 'completed', 'busy', 'failed', 'no-answer', 'canceled'];
    const endedReasons = [
      'customer-ended-call',
      'assistant-ended-call',
      'max-duration-reached',
      'voicemail-detected',
      'error',
    ];
    const successEvaluations = ['success', 'fail', 'partial'];
    
    const calls = [];
    const now = new Date();
    
    for (let i = 0; i < 50; i++) {
      const createdAt = new Date(now.getTime() - Math.random() * 30 * 24 * 60 * 60 * 1000);
      const startedAt = new Date(createdAt.getTime() + Math.random() * 5000);
      const duration = Math.floor(Math.random() * 600) + 10; // 10-610 seconds
      const endedAt = new Date(startedAt.getTime() + duration * 1000);
      
      const type = types[Math.floor(Math.random() * types.length)];
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      const endedReason = endedReasons[Math.floor(Math.random() * endedReasons.length)];
      const successEvaluation = successEvaluations[Math.floor(Math.random() * successEvaluations.length)];
      
      calls.push({
        id: `call_${i + 1}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        orgId: 'org_123456',
        createdAt: createdAt.toISOString(),
        updatedAt: endedAt.toISOString(),
        type,
        status,
        endedReason,
        endedMessage: endedReason === 'error' ? 'Connection timeout' : null,
        startedAt: startedAt.toISOString(),
        endedAt: endedAt.toISOString(),
        cost: parseFloat((Math.random() * 2).toFixed(4)),
        assistantId: `assistant_${Math.floor(Math.random() * 5) + 1}`,
        assistant: {
          id: `assistant_${Math.floor(Math.random() * 5) + 1}`,
          name: ['Riley', 'Alex', 'Sam', 'Jordan', 'Taylor'][Math.floor(Math.random() * 5)],
        },
        customer: type !== 'webCall' ? {
          number: `+1${Math.floor(Math.random() * 9000000000) + 1000000000}`,
        } : null,
        phoneNumber: type !== 'webCall' ? {
          number: `+1${Math.floor(Math.random() * 9000000000) + 1000000000}`,
        } : null,
        duration: `${duration}s`,
        durationSeconds: duration,
        successEvaluation,
        score: successEvaluation === 'success' ? Math.floor(Math.random() * 30) + 70 : 
               successEvaluation === 'partial' ? Math.floor(Math.random() * 30) + 40 : 
               Math.floor(Math.random() * 40),
        recordingUrl: status === 'completed' ? `https://example.com/recordings/call_${i + 1}.wav` : null,
        transcript: status === 'completed' ? this.generateTranscript() : null,
        messages: status === 'completed' ? this.generateMessages() : null,
        analysis: status === 'completed' ? {
          summary: 'Customer called to inquire about product pricing. Assistant provided detailed information and answered all questions satisfactorily.',
          sentiment: 'positive',
        } : null,
      });
    }
    
    return calls.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }

  /**
   * Generate mock transcript
   */
  private generateTranscript() {
    return `[00:00] Assistant: Hello! Thank you for calling. How can I assist you today?

[00:05] Customer: Hi, I'm interested in learning more about your pricing plans.

[00:10] Assistant: I'd be happy to help you with that. We offer several pricing tiers. Our basic plan starts at $29 per month and includes...

[00:25] Customer: That sounds good. What about the premium plan?

[00:28] Assistant: Our premium plan is $79 per month and includes all the features of the basic plan plus priority support, advanced analytics, and...

[00:45] Customer: Great! Can I try it before committing?

[00:48] Assistant: Absolutely! We offer a 14-day free trial for all plans. Would you like me to set that up for you?

[00:55] Customer: Yes, please!

[01:00] Assistant: Perfect! I've started your free trial. You'll receive an email confirmation shortly. Is there anything else I can help you with today?

[01:08] Customer: No, that's all. Thank you!

[01:10] Assistant: You're welcome! Have a great day!`;
  }

  /**
   * Generate mock messages
   */
  private generateMessages() {
    return [
      {
        role: 'assistant',
        content: 'Hello! Thank you for calling. How can I assist you today?',
        timestamp: '00:00',
      },
      {
        role: 'user',
        content: "Hi, I'm interested in learning more about your pricing plans.",
        timestamp: '00:05',
      },
      {
        role: 'assistant',
        content: "I'd be happy to help you with that. We offer several pricing tiers. Our basic plan starts at $29 per month and includes...",
        timestamp: '00:10',
      },
      {
        role: 'user',
        content: 'That sounds good. What about the premium plan?',
        timestamp: '00:25',
      },
      {
        role: 'assistant',
        content: 'Our premium plan is $79 per month and includes all the features of the basic plan plus priority support, advanced analytics, and...',
        timestamp: '00:28',
      },
      {
        role: 'user',
        content: 'Great! Can I try it before committing?',
        timestamp: '00:45',
      },
      {
        role: 'assistant',
        content: "Absolutely! We offer a 14-day free trial for all plans. Would you like me to set that up for you?",
        timestamp: '00:48',
      },
      {
        role: 'user',
        content: 'Yes, please!',
        timestamp: '00:55',
      },
      {
        role: 'assistant',
        content: "Perfect! I've started your free trial. You'll receive an email confirmation shortly. Is there anything else I can help you with today?",
        timestamp: '01:00',
      },
      {
        role: 'user',
        content: "No, that's all. Thank you!",
        timestamp: '01:08',
      },
      {
        role: 'assistant',
        content: "You're welcome! Have a great day!",
        timestamp: '01:10',
      },
    ];
  }
}

