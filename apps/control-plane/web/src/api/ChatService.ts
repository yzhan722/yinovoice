// Mock data service for Chat History
export class ChatService {
  /**
   * Get chat/session list with pagination
   */
  getChatList(params: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const { current = 1, pageSize = 10 } = params;
        const mockChats = this.generateMockChats();
        const start = (current - 1) * pageSize;
        const end = start + pageSize;
        const list = mockChats.slice(start, end);
        
        resolve({
          list,
          total: mockChats.length,
          current,
          pageSize,
        });
      }, 300);
    });
  }

  /**
   * Get chat detail by session ID
   */
  getChatDetail(sessionId: string) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const chat = this.generateMockChats().find(c => c.sessionId === sessionId);
        if (chat) {
          resolve({
            ...chat,
            messages: this.generateMessages(),
          });
        } else {
          resolve(null);
        }
      }, 200);
    });
  }

  /**
   * Generate mock chats data
   */
  private generateMockChats() {
    const statuses = ['active', 'completed', 'failed'];
    const chats = [];
    const now = new Date();
    
    for (let i = 0; i < 30; i++) {
      const startTime = new Date(now.getTime() - Math.random() * 30 * 24 * 60 * 60 * 1000);
      const duration = Math.floor(Math.random() * 1800) + 60; // 60-1860 seconds
      const endTime = new Date(startTime.getTime() + duration * 1000);
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      const messageCount = Math.floor(Math.random() * 50) + 5;
      
      chats.push({
        sessionId: `session_${i + 1}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        assistantId: `assistant_${Math.floor(Math.random() * 5) + 1}`,
        assistantName: ['Riley', 'Alex', 'Sam', 'Jordan', 'Taylor'][Math.floor(Math.random() * 5)],
        startTime: startTime.toISOString(),
        endTime: status === 'completed' ? endTime.toISOString() : null,
        duration: `${Math.floor(duration / 60)}m ${duration % 60}s`,
        durationSeconds: duration,
        status,
        messageCount,
        messages: status === 'completed' ? this.generateMessages() : [],
      });
    }
    
    return chats.sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime());
  }

  /**
   * Generate mock messages
   */
  private generateMessages() {
    const messages = [];
    const roles = ['assistant', 'user'];
    const contents = [
      'Hello! How can I help you today?',
      "I'm looking for information about your services.",
      'I can provide you with detailed information about our services. What specifically would you like to know?',
      'Do you offer customer support?',
      'Yes, we offer 24/7 customer support. Our team is available around the clock to assist you.',
      'That sounds great! How do I contact support?',
      'You can reach our support team via email at support@example.com, or through our live chat feature on our website.',
      'Perfect! Thank you for the information.',
      "You're welcome! Is there anything else I can help you with?",
      'No, that\'s all. Have a great day!',
      'Thank you! Have a wonderful day!',
    ];
    
    for (let i = 0; i < contents.length; i++) {
      messages.push({
        role: roles[i % 2],
        content: contents[i],
        timestamp: new Date(Date.now() - (contents.length - i) * 10000).toISOString(),
      });
    }
    
    return messages;
  }
}

