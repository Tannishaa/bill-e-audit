import { FileText, Loader2, AlertCircle, CheckCircle, Info, Database, CloudRain, Cpu } from "lucide-react";
import AdminZone from "./components/AdminZone";
import AutoRefresh from "./components/AutoRefresh";

type AuditRecord = {
  Filename: string;
  RiskScore: number;
  RiskFlags: string[] | string;
  ExtractedText: string;
  Status: string;
  UploadDate: string;
};

async function getLedgerData(): Promise<AuditRecord[]> {
  try {
    const res = await fetch(process.env.NEXT_PUBLIC_API_URL as string, { cache: 'no-store' });
    if (!res.ok) return [];
    const data: AuditRecord[] = await res.json();
    
    return data.sort((a, b) => {
      const dateB = b.UploadDate ? new Date(b.UploadDate).getTime() : 0;
      const dateA = a.UploadDate ? new Date(a.UploadDate).getTime() : 0;
      return dateB - dateA;
    });
  } catch {
    return [];
  }
}

function getStatusUI(status: string) {
  if (status.includes("Error")) return { color: "text-red-500", icon: <AlertCircle className="w-3.5 h-3.5 inline mr-1.5" /> };
  if (status === "Processing") return { color: "text-zinc-400 animate-pulse", icon: <Loader2 className="w-3.5 h-3.5 inline mr-1.5 animate-spin" /> };
  if (status === "Queued") return { color: "text-zinc-500", icon: <Database className="w-3.5 h-3.5 inline mr-1.5" /> };
  return { color: "text-zinc-300", icon: <CheckCircle className="w-3.5 h-3.5 inline mr-1.5" /> };
}

export default async function Dashboard() {
  const data = await getLedgerData();
  const processedCount = data.filter(d => d.Status === 'Analyzed').length;

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-zinc-300 p-8 font-sans selection:bg-zinc-800">
      <AutoRefresh interval={3000} /> 
      
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header Section */}
        <header className="border-b border-zinc-800 pb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
          <div>
            <h1 className="text-3xl font-medium tracking-tight text-zinc-100 flex items-center gap-3">
              <FileText className="w-6 h-6 text-zinc-400" />
              Bill-E Audit Ledger
            </h1>
            <p className="text-zinc-500 mt-2 text-sm tracking-wide">Production event-driven ingestion & OCR analysis.</p>
          </div>
        </header>

        {/* Architecture Description Section */}
        <details className="group bg-zinc-900/50 border border-zinc-800 rounded-sm p-4 text-sm open:pb-6 transition-all duration-200">
          <summary className="font-medium text-zinc-300 cursor-pointer list-none flex items-center gap-2 select-none">
            <Info className="w-4 h-4 text-zinc-500" />
            About this Pipeline
            <span className="text-zinc-600 ml-auto text-xs group-open:hidden">Click to expand</span>
          </summary>
          <div className="mt-4 text-zinc-400 leading-relaxed space-y-3 pl-6 border-l border-zinc-800 ml-2">
            <p>This dashboard visualizes a live, zero-idle-cost serverless backend built on AWS.</p>
            <ul className="space-y-2 text-zinc-500 flex flex-col gap-1">
              <li className="flex items-center gap-2"><CloudRain className="w-3.5 h-3.5 text-zinc-600"/> <strong>1. Ingestion:</strong> Files uploaded via this UI are securely stored in an Amazon S3 bucket.</li>
              <li className="flex items-center gap-2"><Database className="w-3.5 h-3.5 text-zinc-600"/> <strong>2. Orchestration:</strong> S3 triggers an event notification, placing the audit request into an Amazon SQS queue.</li>
              <li className="flex items-center gap-2"><Cpu className="w-3.5 h-3.5 text-zinc-600"/> <strong>3. Compute & AI:</strong> A Python AWS Lambda function polls the queue, extracts text via OCR, and runs heuristic risk analysis.</li>
              <li className="flex items-center gap-2"><FileText className="w-3.5 h-3.5 text-zinc-600"/> <strong>4. Storage:</strong> Final risk scores and extracted data are written to DynamoDB, which is polled by this Next.js interface.</li>
            </ul>
          </div>
        </details>

        {/* Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[#0f0f0f] p-5 border border-zinc-800 flex justify-between items-center">
            <h3 className="text-zinc-500 text-xs font-medium uppercase tracking-widest">Total Ingested</h3>
            <p className="text-2xl font-normal text-zinc-100">{data.length}</p>
          </div>
          <div className="bg-[#0f0f0f] p-5 border border-zinc-800 flex justify-between items-center">
            <h3 className="text-zinc-500 text-xs font-medium uppercase tracking-widest">Successfully Analyzed</h3>
            <p className="text-2xl font-normal text-zinc-100">{processedCount}</p>
          </div>
        </div>

        {/* Audit Table */}
        <div className="bg-[#0f0f0f] border border-zinc-800 overflow-hidden">
          {data.length === 0 ? (
            <div className="p-16 text-center text-zinc-600 text-sm font-mono uppercase tracking-widest">Ledger is empty</div>
          ) : (
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-[#141414] border-b border-zinc-800 text-zinc-500 text-xs uppercase tracking-wider font-medium">
                <tr>
                  <th className="px-6 py-4">Receipt ID</th>
                  <th className="px-6 py-4">Pipeline Status</th>
                  <th className="px-6 py-4">Risk Score</th>
                  <th className="px-6 py-4 w-full">Heuristic Flags</th>
                  <th className="px-6 py-4 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {data.map((row, idx) => {
                  const ui = getStatusUI(row.Status || 'Queued');
                  const flags = Array.isArray(row.RiskFlags) ? row.RiskFlags : (row.RiskFlags ? [row.RiskFlags] : []);
                  const isHighRisk = row.RiskScore > 50;
                  
                  return (
                    <tr key={row.UploadDate ? `${row.Filename}-${row.UploadDate}` : `pending-${idx}`} className="hover:bg-[#141414] transition-colors">
                      <td className="px-6 py-4 font-mono text-[11px] text-zinc-400 max-w-[150px] truncate" title={row.Filename}>
                        {row.Filename}
                      </td>
                      <td className="px-6 py-4 text-[12px] font-medium tracking-wide">
                        <span className={`flex items-center ${ui.color}`}>
                          {ui.icon} {row.Status || 'Queued'}
                        </span>
                      </td>
                      <td className={`px-6 py-4 font-mono text-[13px] ${isHighRisk ? 'text-red-500 font-medium' : 'text-zinc-400'}`}>
                       {Number(row.RiskScore || 0).toFixed(2)}
                      </td>
                      <td className="px-6 py-4">
                        {flags.length > 0 && flags[0] !== "None" ? (
                          <div className="flex flex-wrap gap-2">
                            {flags.map((flag, i) => (
                              <span key={i} className="bg-red-950/20 text-red-400 px-2 py-0.5 border border-red-900/30 text-[10px] uppercase tracking-wider font-mono">
                                {flag.replace('Suspicious Item: ', '')}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-zinc-600 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-zinc-500 font-mono text-[11px] text-right">
                        {row.UploadDate ? new Date(row.UploadDate).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : '...'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Upload Engine */}
        <div className="mt-16 pt-8 border-t border-zinc-800">
          <h2 className="text-lg font-medium tracking-tight text-zinc-300 mb-6 flex items-center gap-2">
            Manual Ingestion Route
          </h2>
          <AdminZone />
        </div>
      </div>
    </main>
  );
}