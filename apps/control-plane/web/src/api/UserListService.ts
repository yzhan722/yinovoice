// Mock data service for User List (Admin)
export class UserListService {
  /**
   * Get user list with pagination
   */
  getUserList(params: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const { current = 1, pageSize = 10 } = params;
        const mockUsers = this.generateMockUsers();
        const start = (current - 1) * pageSize;
        const end = start + pageSize;
        const list = mockUsers.slice(start, end);
        
        resolve({
          list,
          total: mockUsers.length,
          current,
          pageSize,
        });
      }, 300);
    });
  }

  /**
   * Get user detail by ID
   */
  getUserDetail(userId: string) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const user = this.generateMockUsers().find(u => u.userId === userId);
        resolve(user || null);
      }, 200);
    });
  }

  /**
   * Update user
   */
  updateUser(userId: string, data: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          success: true,
          userId,
          ...data,
        });
      }, 300);
    });
  }

  /**
   * Delete user
   */
  deleteUser(userId: string) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          success: true,
          userId,
        });
      }, 300);
    });
  }

  /**
   * Generate mock users data
   */
  private generateMockUsers() {
    const firstNames = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'Robert', 'Jessica', 'William', 'Ashley'];
    const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez'];
    const domains = ['example.com', 'test.com', 'demo.com', 'sample.org'];
    const statuses = ['active', 'inactive'];
    
    const users = [];
    const now = new Date();
    
    for (let i = 0; i < 25; i++) {
      const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
      const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
      const email = `${firstName.toLowerCase()}.${lastName.toLowerCase()}@${domains[Math.floor(Math.random() * domains.length)]}`;
      const phone = `+1${Math.floor(Math.random() * 9000000000) + 1000000000}`;
      const createdAt = new Date(now.getTime() - Math.random() * 365 * 24 * 60 * 60 * 1000);
      
      users.push({
        userId: `user_${i + 1}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        userName: `${firstName} ${lastName}`,
        email,
        phone,
        status: statuses[Math.floor(Math.random() * statuses.length)],
        createTime: createdAt.toISOString(),
        createdAt: createdAt.toISOString(),
      });
    }
    
    return users.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }
}

