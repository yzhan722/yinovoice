// Mock data service for Knowledge Base Files
export class FileService {
  /**
   * Get file list with pagination
   */
  getFileList(params: any) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const { current = 1, pageSize = 10, sortBy = 'name' } = params;
        let mockFiles = this.generateMockFiles();
        
        // Sort files
        if (sortBy === 'name') {
          mockFiles.sort((a, b) => a.name.localeCompare(b.name));
        } else if (sortBy === 'time') {
          mockFiles.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
        }
        
        const start = (current - 1) * pageSize;
        const end = start + pageSize;
        const list = mockFiles.slice(start, end);
        
        resolve({
          list,
          total: mockFiles.length,
          current,
          pageSize,
        });
      }, 300);
    });
  }

  /**
   * Upload file
   */
  uploadFile(file: File) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const newFile = {
          id: `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          orgId: 'org_123456',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          object: 'file',
          status: 'done',
          name: file.name,
          originalName: file.name,
          bytes: file.size,
          mimetype: file.type,
          url: URL.createObjectURL(file),
        };
        
        resolve(newFile);
      }, 1000);
    });
  }

  /**
   * Delete file
   */
  deleteFile(fileId: string) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ success: true, fileId });
      }, 300);
    });
  }

  /**
   * Generate mock files data
   */
  private generateMockFiles() {
    const fileTypes = ['pdf', 'docx', 'txt', 'csv'];
    const fileNames = [
      'Product Catalog 2024',
      'Customer Service Guidelines',
      'Pricing Information',
      'FAQ Document',
      'Training Manual',
      'Company Policies',
      'Technical Specifications',
      'User Guide',
      'Installation Instructions',
      'Troubleshooting Guide',
      'API Documentation',
      'Best Practices',
      'Sales Process',
      'Marketing Materials',
      'Support Procedures',
    ];
    
    const files = [];
    const now = new Date();
    
    for (let i = 0; i < fileNames.length; i++) {
      const type = fileTypes[Math.floor(Math.random() * fileTypes.length)];
      const size = Math.floor(Math.random() * 5000000) + 100000; // 100KB - 5MB
      const createdAt = new Date(now.getTime() - Math.random() * 90 * 24 * 60 * 60 * 1000);
      
      files.push({
        id: `file_${i + 1}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        orgId: 'org_123456',
        createdAt: createdAt.toISOString(),
        updatedAt: createdAt.toISOString(),
        object: 'file',
        status: 'done',
        name: `${fileNames[i]}.${type}`,
        originalName: `${fileNames[i]}.${type}`,
        fileType: type.toUpperCase(),
        fileSize: size,
        bytes: size,
        mimetype: this.getMimeType(type),
        url: `https://example.com/files/${fileNames[i]}.${type}`,
        downloadUrl: `https://example.com/files/${fileNames[i]}.${type}?download=true`,
        uploadTime: createdAt.toISOString(),
      });
    }
    
    return files;
  }

  /**
   * Get MIME type by file extension
   */
  private getMimeType(ext: string): string {
    const mimeTypes: Record<string, string> = {
      pdf: 'application/pdf',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      txt: 'text/plain',
      csv: 'text/csv',
    };
    return mimeTypes[ext] || 'application/octet-stream';
  }
}

