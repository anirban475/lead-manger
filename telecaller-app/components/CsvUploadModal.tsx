'use client';

import { useState, useEffect, useTransition } from 'react';
import Papa from 'papaparse';
import { TARGET_FIELDS, guessMapping, validateRow } from '@/lib/csv';
import { normalizePhones } from '@/lib/phone';
import { getExistingContactIndex } from '@/actions/getExistingContactIndex';
import { bulkCreateLeads } from '@/actions/bulkCreateLeads';

type CsvUploadModalProps = {
  onClose: () => void;
  onSuccess: () => void;
};

type Step = 'upload' | 'map' | 'validate' | 'result';

type RowData = {
  company_name: string;
  contact_phone: string;
  contact_email: string;
  contact_name: string;
  contact_title: string;
  city: string;
  // Local status flags
  status: 'valid' | 'error' | 'duplicate';
  errorReason?: string;
  skipped: boolean;
};

export default function CsvUploadModal({ onClose, onSuccess }: CsvUploadModalProps) {
  const [step, setStep] = useState<Step>('upload');
  const [fileError, setFileError] = useState<string | null>(null);
  
  // Step 1: Parse State
  const [parsedHeaders, setParsedHeaders] = useState<string[]>([]);
  const [parsedData, setParsedData] = useState<any[]>([]);

  // Step 2: Mapping State
  const [mapping, setMapping] = useState<Record<string, string>>({});

  // Step 3: Validation State
  const [rows, setRows] = useState<RowData[]>([]);
  const [loadingIndex, setLoadingIndex] = useState(false);
  const [dbIndex, setDbIndex] = useState<{ phones: string[]; companies: string[] }>({ phones: [], companies: [] });
  
  // Step 4: Import Result State
  const [isPending, startTransition] = useTransition();
  const [importResult, setImportResult] = useState<{
    inserted: number;
    skippedDuplicates: number;
    failed: { index: number; reason: string }[];
  } | null>(null);

  // Trigger Template Download
  const handleDownloadTemplate = () => {
    const headers = TARGET_FIELDS.map(f => `"${f.label}"`).join(',');
    const sample = '\n"Acme Corp","+91 98765 43210","hr@acme.com","John Doe","HR Manager","Mumbai"';
    const csvContent = headers + sample;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'lead_import_template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Handle File Upload & Parse
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (results.errors.length > 0 && results.data.length === 0) {
          setFileError('Failed to parse CSV file. Ensure it is a valid CSV format.');
          return;
        }

        const data = results.data as Record<string, any>[];
        if (data.length === 0) {
          setFileError('The uploaded CSV file is empty.');
          return;
        }

        if (data.length > 5000) {
          setFileError('File exceeds the limit of 5,000 rows. Please split your upload.');
          return;
        }

        // Extract headers from first parsed row keys
        const headers = Object.keys(data[0]);
        setParsedHeaders(headers);
        setParsedData(data);
        
        // Auto-guess column mappings
        setMapping(guessMapping(headers));
        setStep('map');
      },
      error: (err) => {
        setFileError(`Parse error: ${err.message}`);
      }
    });
  };

  // ADVANCE TO STEP 3: Load existing lead registry & map rows
  const handleAdvanceToValidation = async () => {
    setLoadingIndex(true);
    setStep('validate');
    try {
      const index = await getExistingContactIndex();
      setDbIndex(index);
      processRows(parsedData, mapping, index);
    } catch (err) {
      console.error(err);
      setFileError('Failed to load deduplication index from server.');
      setStep('map');
    } finally {
      setLoadingIndex(false);
    }
  };

  // Process mapping + validate & dedupe
  const processRows = (rawList: any[], fieldMap: Record<string, string>, index: { phones: string[]; companies: string[] }) => {
    const dbPhones = new Set(index.phones);
    const dbCompanies = new Set(index.companies);
    
    const filePhones = new Set<string>();
    const fileCompanies = new Set<string>();

    const mappedRows: RowData[] = rawList.map((rawRow) => {
      const company_name = String(rawRow[fieldMap.company_name] || '').trim();
      const contact_phone = String(rawRow[fieldMap.contact_phone] || '').trim();
      const contact_email = String(rawRow[fieldMap.contact_email] || '').trim();
      const contact_name = String(rawRow[fieldMap.contact_name] || '').trim();
      const contact_title = String(rawRow[fieldMap.contact_title] || '').trim();
      const city = String(rawRow[fieldMap.city] || '').trim();

      const validation = validateRow({ company_name, contact_phone });
      
      let status: 'valid' | 'error' | 'duplicate' = validation.valid ? 'valid' : 'error';
      let errorReason = validation.reason;
      let skipped = false;

      if (validation.valid) {
        const normalizedPhones = normalizePhones(contact_phone);
        const compLower = company_name.toLowerCase().trim();

        // 1. Check duplicate against DB index
        let isDupe = dbCompanies.has(compLower);
        for (const p of normalizedPhones) {
          if (dbPhones.has(p.e164)) {
            isDupe = true;
            break;
          }
        }

        // 2. Check duplicate within the file
        if (fileCompanies.has(compLower)) {
          isDupe = true;
        }
        for (const p of normalizedPhones) {
          if (filePhones.has(p.e164)) {
            isDupe = true;
            break;
          }
        }

        if (isDupe) {
          status = 'duplicate';
          skipped = true;
        } else {
          // Record in batch registry
          fileCompanies.add(compLower);
          for (const p of normalizedPhones) {
            filePhones.add(p.e164);
          }
        }
      }

      return {
        company_name,
        contact_phone,
        contact_email,
        contact_name,
        contact_title,
        city,
        status,
        errorReason,
        skipped
      };
    });

    setRows(mappedRows);
  };

  // Re-run validation on individual row cell edit
  const handleCellEdit = (index: number, field: keyof RowData, value: string) => {
    setRows(prevRows => {
      const updated = [...prevRows];
      updated[index] = { ...updated[index], [field]: value };
      
      // Re-run validation on edit
      const validation = validateRow({
        company_name: updated[index].company_name,
        contact_phone: updated[index].contact_phone
      });

      if (!validation.valid) {
        updated[index].status = 'error';
        updated[index].errorReason = validation.reason;
      } else {
        // Check for duplicates
        const normalizedPhones = normalizePhones(updated[index].contact_phone);
        const compLower = updated[index].company_name.toLowerCase().trim();
        
        let isDupe = dbIndex.companies.includes(compLower);
        for (const p of normalizedPhones) {
          if (dbIndex.phones.includes(p.e164)) {
            isDupe = true;
            break;
          }
        }

        // Check file duplicates (simple scan excluding current row)
        for (let j = 0; j < updated.length; j++) {
          if (j === index) continue;
          if (updated[j].status === 'error') continue;
          if (updated[j].company_name.toLowerCase().trim() === compLower) {
            isDupe = true;
          }
          const otherPhones = normalizePhones(updated[j].contact_phone);
          for (const p of normalizedPhones) {
            if (otherPhones.some(op => op.e164 === p.e164)) {
              isDupe = true;
            }
          }
        }

        if (isDupe) {
          updated[index].status = 'duplicate';
          updated[index].skipped = true;
          updated[index].errorReason = undefined;
        } else {
          updated[index].status = 'valid';
          updated[index].skipped = false;
          updated[index].errorReason = undefined;
        }
      }
      return updated;
    });
  };

  // Toggle duplicate skip override
  const handleToggleSkip = (index: number) => {
    setRows(prevRows => {
      const updated = [...prevRows];
      updated[index] = { ...updated[index], skipped: !updated[index].skipped };
      return updated;
    });
  };

  // Perform Server Action Bulk Import
  const handleImport = () => {
    const importPayload = rows
      .filter(r => r.status !== 'error' && !r.skipped)
      .map(r => ({
        company_name: r.company_name,
        contact_phone: r.contact_phone,
        contact_email: r.contact_email || null,
        contact_name: r.contact_name || null,
        contact_title: r.contact_title || null,
        city: r.city || null
      }));

    startTransition(async () => {
      try {
        const res = await bulkCreateLeads(importPayload);
        setImportResult(res);
        setStep('result');
        if (res.inserted > 0) {
          onSuccess(); // Trigger router refresh
        }
      } catch (err: any) {
        alert(err.message || 'Import failed');
      }
    });
  };

  // Counts
  const errorCount = rows.filter(r => r.status === 'error').length;
  const dupeCount = rows.filter(r => r.status === 'duplicate').length;
  const validCount = rows.filter(r => r.status === 'valid').length;
  const finalImportCount = rows.filter(r => r.status !== 'error' && !r.skipped).length;

  return (
    <>
      <div className="drawer-backdrop active" onClick={onClose} style={{ zIndex: 110 }} />
      <div 
        className="card pad" 
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '95%',
          maxWidth: step === 'validate' ? '860px' : '620px',
          maxHeight: '90vh',
          overflowY: 'auto',
          zIndex: 120,
          background: 'var(--surface-card)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
          border: '1px solid var(--border-default)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>
            Bulk Lead Import — Step {step === 'upload' ? '1/4' : step === 'map' ? '2/4' : step === 'validate' ? '3/4' : '4/4'}
          </h2>
          <button 
            type="button" 
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', fontSize: '20px', cursor: 'pointer', color: 'var(--text-muted)' }}
          >
            ✕
          </button>
        </div>

        {/* STEP 1: Upload */}
        {step === 'upload' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <p className="muted" style={{ margin: 0, fontSize: '14px' }}>
              Drop in a CSV list of leads to add them in bulk to your telecaller queue.
            </p>
            <div 
              style={{
                border: '2px dashed var(--border-strong)',
                borderRadius: 'var(--radius-sm)',
                padding: '40px 20px',
                textAlign: 'center',
                background: 'var(--surface-sunken)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px'
              }}
            >
              <input 
                type="file" 
                accept=".csv" 
                onChange={handleFileChange}
                style={{ display: 'none' }}
                id="csv-file-input"
              />
              <label 
                htmlFor="csv-file-input" 
                className="btn primary"
                style={{ cursor: 'pointer', display: 'inline-flex' }}
              >
                Choose CSV File
              </label>
              <span className="text-muted" style={{ fontSize: '12px' }}>
                Supports BOM, quoted values, and up to 5,000 rows.
              </span>
            </div>

            {fileError && (
              <div className="form-error animate-fade-in" style={{ padding: '8px 12px', background: 'var(--color-danger-bg)', borderRadius: 'var(--radius-sm)', fontSize: '13px' }}>
                ⚠️ {fileError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border-default)', paddingTop: '14px' }}>
              <button type="button" onClick={handleDownloadTemplate} className="btn ghost" style={{ fontSize: '13px', padding: '6px 12px' }}>
                ⬇ Download CSV template
              </button>
              <button type="button" onClick={onClose} className="btn secondary" style={{ fontSize: '13px', padding: '6px 12px' }}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Map Fields */}
        {step === 'map' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <p className="muted" style={{ margin: 0, fontSize: '14px' }}>
              Map target Lead Fields to columns in your uploaded CSV.
            </p>
            <div className="table-responsive" style={{ margin: 0 }}>
              <table className="dense-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Lead Field</th>
                    <th>CSV Column Source</th>
                  </tr>
                </thead>
                <tbody>
                  {TARGET_FIELDS.map((field) => (
                    <tr key={field.key}>
                      <td style={{ fontWeight: 600 }}>
                        {field.label} {field.required && <span style={{ color: 'var(--color-danger)' }}>*</span>}
                      </td>
                      <td>
                        <select 
                          className="input" 
                          value={mapping[field.key] || ''}
                          onChange={(e) => setMapping(prev => ({ ...prev, [field.key]: e.target.value }))}
                          style={{ padding: '4px 8px', fontSize: '13px' }}
                        >
                          <option value="">-- Skip Field --</option>
                          {parsedHeaders.map(h => (
                            <option key={h} value={h}>{h}</option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {(!mapping.company_name || !mapping.contact_phone) && (
              <div className="form-error" style={{ fontSize: '13px', padding: '6px 12px', background: 'var(--color-danger-bg)', borderRadius: 'var(--radius-sm)' }}>
                ⚠️ Please map the required fields: <strong>Company Name</strong> and <strong>Phone Number(s)</strong>.
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', borderTop: '1px solid var(--border-default)', paddingTop: '14px' }}>
              <button type="button" onClick={() => setStep('upload')} className="btn secondary" style={{ padding: '6px 12px', fontSize: '13px' }}>Back</button>
              <button 
                type="button" 
                onClick={handleAdvanceToValidation} 
                className="btn primary" 
                disabled={!mapping.company_name || !mapping.contact_phone}
                style={{ padding: '6px 12px', fontSize: '13px' }}
              >
                Validate Rows
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Preview, Validate & Edit */}
        {step === 'validate' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {loadingIndex ? (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                Loading duplication index from server...
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '10px', fontSize: '13px' }}>
                    <span className="badge" style={{ background: 'var(--color-success-bg)', color: 'var(--color-success)', fontWeight: 600 }}>{validCount} ready</span>
                    {errorCount > 0 && <span className="badge" style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)', fontWeight: 600 }}>{errorCount} to fix</span>}
                    {dupeCount > 0 && <span className="badge" style={{ background: 'var(--color-warning-bg)', color: 'var(--color-warning)', fontWeight: 600 }}>{dupeCount} duplicates</span>}
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600 }}>
                    Final Import Payload: <span style={{ color: 'var(--color-primary-strong)' }}>{finalImportCount} rows</span>
                  </div>
                </div>

                <div className="table-responsive" style={{ maxHeight: '42vh', overflowY: 'auto', margin: 0 }}>
                  <table className="dense-table" style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        <th style={{ width: '120px' }}>Row Status</th>
                        <th>Company Name</th>
                        <th>Phone Number(s)</th>
                        <th>Email</th>
                        <th>Contact Person</th>
                        <th>City</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, idx) => (
                        <tr key={idx} style={{ background: row.status === 'error' ? 'rgba(239, 68, 68, 0.05)' : row.status === 'duplicate' ? 'rgba(245, 158, 11, 0.03)' : 'inherit' }}>
                          <td>
                            {row.status === 'error' && (
                              <span style={{ color: 'var(--color-danger)', fontWeight: 'bold', fontSize: '11px', display: 'block' }} title={row.errorReason}>
                                ❌ {row.errorReason}
                              </span>
                            )}
                            {row.status === 'duplicate' && (
                              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontSize: '11px' }}>
                                <input 
                                  type="checkbox" 
                                  checked={row.skipped} 
                                  onChange={() => handleToggleSkip(idx)} 
                                />
                                <span style={{ color: 'var(--color-warning)', fontWeight: 'bold' }}>Duplicate (skip)</span>
                              </label>
                            )}
                            {row.status === 'valid' && (
                              <span style={{ color: 'var(--color-success)', fontWeight: 'bold', fontSize: '11px' }}>
                                ✅ Ready
                              </span>
                            )}
                          </td>
                          <td>
                            {row.status === 'error' && !row.company_name ? (
                              <input 
                                type="text" 
                                className="input" 
                                value={row.company_name} 
                                onChange={(e) => handleCellEdit(idx, 'company_name', e.target.value)} 
                                style={{ padding: '2px 6px', fontSize: '12px' }}
                              />
                            ) : (
                              row.company_name
                            )}
                          </td>
                          <td>
                            {row.status === 'error' ? (
                              <input 
                                type="text" 
                                className="input" 
                                value={row.contact_phone} 
                                onChange={(e) => handleCellEdit(idx, 'contact_phone', e.target.value)} 
                                style={{ padding: '2px 6px', fontSize: '12px' }}
                              />
                            ) : (
                              row.contact_phone
                            )}
                          </td>
                          <td>{row.contact_email || '—'}</td>
                          <td>{row.contact_name ? `${row.contact_name} ${row.contact_title ? `(${row.contact_title})` : ''}` : '—'}</td>
                          <td>{row.city || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {errorCount > 0 && (
                  <div className="form-error" style={{ fontSize: '13px', padding: '6px 12px', background: 'var(--color-danger-bg)', borderRadius: 'var(--radius-sm)' }}>
                    ⚠️ Correct all validation errors (marked with ❌) before starting import. Click bad cells to correct inline.
                  </div>
                )}

                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', borderTop: '1px solid var(--border-default)', paddingTop: '14px' }}>
                  <button type="button" onClick={() => setStep('map')} className="btn secondary" style={{ padding: '6px 12px', fontSize: '13px' }} disabled={isPending}>Back</button>
                  <button 
                    type="button" 
                    onClick={handleImport} 
                    className="btn primary" 
                    disabled={errorCount > 0 || finalImportCount === 0 || isPending}
                    style={{ padding: '6px 12px', fontSize: '13px' }}
                  >
                    {isPending ? 'Importing...' : `Import ${finalImportCount} Leads`}
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* STEP 4: Results */}
        {step === 'result' && importResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} className="animate-fade-in">
            <div style={{ textAlign: 'center', padding: '10px 0' }}>
              <div style={{ fontSize: '48px', marginBottom: '8px' }}>🎉</div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-strong)' }}>Import Completed Successfully</h3>
            </div>

            <div className="card pad" style={{ background: 'var(--surface-sunken)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', padding: '16px', border: 'none' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--color-success)' }}>{importResult.inserted}</div>
                <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600 }}>Leads Imported</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--color-warning)' }}>{importResult.skippedDuplicates}</div>
                <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600 }}>Duplicates Skipped</div>
              </div>
            </div>

            {importResult.failed.length > 0 && (
              <div>
                <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-danger)', marginBottom: '6px' }}>Failed Rows ({importResult.failed.length})</h4>
                <div className="table-responsive" style={{ maxHeight: '180px', overflowY: 'auto' }}>
                  <table className="dense-table" style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        <th>Row Index</th>
                        <th>Error Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importResult.failed.map((fail, fIdx) => (
                        <tr key={fIdx}>
                          <td>Row #{fail.index + 1}</td>
                          <td style={{ color: 'var(--color-danger)' }}>{fail.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-default)', paddingTop: '14px', marginTop: '10px' }}>
              <button type="button" onClick={onClose} className="btn primary" style={{ padding: '8px 24px' }}>
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
