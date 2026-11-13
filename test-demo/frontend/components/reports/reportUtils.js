// Utility functions for Reports module

export function exportToCsv(filename, columns, rows) {
  if (!rows || !rows.length) return;

  // Formula injection prevention characters
  const DANGEROUS_PREFIXES = ['=', '+', '-', '@', '\t', '\r'];

  const escapeCell = (val) => {
    if (val === null || val === undefined) return '""';
    let s = String(val);
    // Neutralize formula injection
    if (s.length > 0 && DANGEROUS_PREFIXES.includes(s[0])) {
      s = `'${s}`;
    }
    // Escape quotes
    return `"${s.replace(/"/g, '""')}"`;
  };

  const headerLine = columns.map(c => escapeCell(c.label || c.key)).join(',');
  const rowLines = rows.map(r => 
    columns.map(c => {
      const val = typeof c.accessor === 'function' ? c.accessor(r) : r[c.key];
      return escapeCell(val);
    }).join(',')
  );

  // UTF-8 with BOM for proper Excel display (including Gujarati and special characters)
  const csvContent = '\uFEFF' + [headerLine, ...rowLines].join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function formatNum(n) {
  if (n === null || n === undefined) return '0';
  return Number(n).toLocaleString('en-IN');
}

export function formatPct(p) {
  if (p === null || p === undefined) return '—';
  return `${Number(p).toFixed(1)}%`;
}

export function formatDateStr(dateStr) {
  if (!dateStr) return '—';
  try {
    const s = String(dateStr).trim().replace('T', ' ');
    const parts = s.split(' ');
    const dateParts = parts[0].split('-');
    if (dateParts.length === 3) {
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const y = dateParts[0];
      const m = months[parseInt(dateParts[1], 10) - 1] || dateParts[1];
      const d = dateParts[2];
      const timePart = parts[1] ? `, ${parts[1].slice(0, 5)}` : '';
      return `${d} ${m} ${y}${timePart}`;
    }
  } catch (e) {
    // fallback to original
  }
  return dateStr;
}

