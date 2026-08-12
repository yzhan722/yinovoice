import * as XLSX from 'xlsx';

export function exportExcel(data: any[][], fileName: string, merges?: any[]) {
  const ws = XLSX.utils.aoa_to_sheet(data);
  if (merges) ws['!merges'] = merges;
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
  XLSX.writeFile(wb, fileName);
} 