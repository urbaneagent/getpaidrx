import React, { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useClaimsStore } from '../../stores/claimsStore';
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  X,
  Download,
} from 'lucide-react';

export default function UploadClaims() {
  const { analyzeCSV, analyzedClaims } = useClaimsStore();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [resultSummary, setResultSummary] = useState<{
    total: number;
    underpaid: number;
    totalAmount: number;
  } | null>(null);

  const processFile = useCallback(async (file: File) => {
    if (!file.name.endsWith('.csv')) {
      alert('Please upload a CSV file.');
      return;
    }
    
    setFileName(file.name);
    setAnalyzing(true);
    setAnalyzed(false);

    const text = await file.text();
    
    // Simulate processing time for UX
    await new Promise(r => setTimeout(r, 1200));
    
    const results = analyzeCSV(text);
    const underpaid = results.filter(c => c.isUnderpaid);
    const totalAmount = underpaid.reduce((sum, c) => sum + (c.underpaymentAmount || 0), 0);

    setResultSummary({
      total: results.length,
      underpaid: underpaid.length,
      totalAmount,
    });
    setAnalyzing(false);
    setAnalyzed(true);
  }, [analyzeCSV]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const downloadSampleCSV = () => {
    const sample = `claimId,ndc,drugName,quantity,dateDispensed,reimbursement,payer
CLM-001,00002-4462-30,Metformin 500mg,90,2026-01-15,0.85,Cigna
CLM-002,00071-0155-23,Lisinopril 10mg,30,2026-01-15,0.52,UnitedHealth
CLM-003,00093-7180-01,Amlodipine 5mg,30,2026-01-16,0.89,Cigna
CLM-004,00378-1800-01,Atorvastatin 20mg,90,2026-01-16,1.50,Aetna
CLM-005,00781-1506-01,Omeprazole 20mg,30,2026-01-17,0.25,UnitedHealth
CLM-006,51991-0747-01,Levothyroxine 50mcg,30,2026-01-17,0.45,Cigna
CLM-007,00591-0405-01,Gabapentin 300mg,90,2026-01-18,3.20,Aetna
CLM-008,65862-0157-01,Sertraline 50mg,30,2026-01-18,0.98,UnitedHealth
CLM-009,00378-3512-01,Losartan 50mg,90,2026-01-19,4.50,Cigna
CLM-010,00093-0058-01,Simvastatin 20mg,30,2026-01-19,0.75,Aetna
CLM-011,68382-0052-10,Montelukast 10mg,30,2026-01-20,1.80,UnitedHealth
CLM-012,65862-0676-01,Escitalopram 10mg,30,2026-01-20,0.85,Cigna
CLM-013,00781-2061-01,Pantoprazole 40mg,90,2026-01-21,1.90,Aetna
CLM-014,42571-0312-10,Clopidogrel 75mg,30,2026-01-21,0.30,UnitedHealth
CLM-015,00093-5264-01,Duloxetine 30mg,60,2026-01-22,2.20,Cigna
CLM-016,68180-0757-01,Rosuvastatin 10mg,30,2026-01-22,0.52,Aetna
CLM-017,00378-6150-01,Tamsulosin 0.4mg,30,2026-01-23,0.35,UnitedHealth
CLM-018,00591-3533-01,Meloxicam 15mg,30,2026-01-23,1.02,Cigna
CLM-019,00093-2263-01,Pregabalin 75mg,60,2026-01-24,3.15,Aetna
CLM-020,00093-3147-01,Amoxicillin 500mg,21,2026-01-24,0.56,UnitedHealth`;

    const blob = new Blob([sample], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample-claims.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Claims</h1>
        <p className="text-gray-600 mt-1">
          Upload your pharmacy claims CSV to detect underpayments against NADAC benchmarks.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`drop-zone ${isDragging ? 'active' : ''} ${analyzed ? 'border-green-300 bg-green-50' : ''}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          className="hidden"
        />

        {analyzing ? (
          <div className="space-y-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto" />
            <p className="text-gray-700 font-medium">Analyzing claims against NADAC database...</p>
            <p className="text-sm text-gray-500">{fileName}</p>
          </div>
        ) : analyzed ? (
          <div className="space-y-4">
            <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto" />
            <p className="text-gray-700 font-medium">Analysis Complete!</p>
            <p className="text-sm text-gray-500">{fileName}</p>
          </div>
        ) : (
          <div className="space-y-4">
            <Upload className={`w-12 h-12 mx-auto ${isDragging ? 'text-primary-600' : 'text-gray-400'}`} />
            <div>
              <p className="text-gray-700 font-medium">
                {isDragging ? 'Drop your CSV here' : 'Drag & drop your claims CSV here'}
              </p>
              <p className="text-sm text-gray-500 mt-1">or click to browse</p>
            </div>
          </div>
        )}
      </div>

      {/* Sample CSV download */}
      <div className="flex items-center justify-center">
        <button
          onClick={downloadSampleCSV}
          className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          <Download className="w-4 h-4" />
          Download Sample CSV (20 claims)
        </button>
      </div>

      {/* Results summary */}
      {resultSummary && (
        <div className="card space-y-6">
          <h2 className="text-lg font-bold text-gray-900">Analysis Results</h2>

          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <p className="text-3xl font-bold text-blue-600">{resultSummary.total}</p>
              <p className="text-sm text-gray-600 mt-1">Total Claims</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-3xl font-bold text-red-600">{resultSummary.underpaid}</p>
              <p className="text-sm text-gray-600 mt-1">Underpaid</p>
            </div>
            <div className="text-center p-4 bg-orange-50 rounded-lg">
              <p className="text-3xl font-bold text-orange-600">
                ${resultSummary.totalAmount.toFixed(2)}
              </p>
              <p className="text-sm text-gray-600 mt-1">Total Owed</p>
            </div>
          </div>

          {resultSummary.underpaid > 0 && (
            <div className="flex items-center gap-3 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
              <p className="text-sm text-yellow-800">
                <strong>{resultSummary.underpaid}</strong> of your {resultSummary.total} claims
                were reimbursed below NADAC. You may be owed <strong>${resultSummary.totalAmount.toFixed(2)}</strong> in additional reimbursement.
              </p>
            </div>
          )}

          <button
            onClick={() => navigate('/dashboard/results')}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            View Detailed Results
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* CSV format guide */}
      <div className="card">
        <h3 className="text-sm font-bold text-gray-900 mb-3">CSV Format</h3>
        <p className="text-xs text-gray-500 mb-3">
          Your CSV should include these columns (headers are flexible):
        </p>
        <div className="bg-gray-50 rounded-lg p-4 overflow-x-auto">
          <table className="text-xs text-gray-600 w-full">
            <thead>
              <tr className="text-left border-b border-gray-200">
                <th className="pb-2 pr-4 font-semibold">Column</th>
                <th className="pb-2 pr-4 font-semibold">Description</th>
                <th className="pb-2 font-semibold">Example</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr><td className="py-1.5 pr-4 font-mono">claimId</td><td className="pr-4">Unique claim identifier</td><td>CLM-001</td></tr>
              <tr><td className="py-1.5 pr-4 font-mono">ndc</td><td className="pr-4">National Drug Code</td><td>00002-4462-30</td></tr>
              <tr><td className="py-1.5 pr-4 font-mono">drugName</td><td className="pr-4">Drug name & strength</td><td>Metformin 500mg</td></tr>
              <tr><td className="py-1.5 pr-4 font-mono">quantity</td><td className="pr-4">Units dispensed</td><td>90</td></tr>
              <tr><td className="py-1.5 pr-4 font-mono">dateDispensed</td><td className="pr-4">Dispense date</td><td>2026-01-15</td></tr>
              <tr><td className="py-1.5 pr-4 font-mono">reimbursement</td><td className="pr-4">Amount paid ($)</td><td>0.85</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
