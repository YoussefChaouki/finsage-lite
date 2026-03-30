/**
 * TableChunkView — renders table chunks.
 *
 * If structured tableData is provided, renders a proper <table>.
 * Otherwise, falls back to pre-wrapped monospace text.
 */

interface TableData {
  headers: string[];
  rows: Record<string, unknown>[];
}

interface TableChunkViewProps {
  content: string;
  tableTitle?: string;
  tableData?: TableData;
}

export function TableChunkView({
  content,
  tableTitle,
  tableData,
}: TableChunkViewProps) {
  if (tableData) {
    return (
      <div className="overflow-x-auto rounded-lg border border-slate-700">
        {tableTitle && (
          <div className="border-b border-slate-700 bg-slate-800/60 px-3 py-2">
            <span className="text-xs font-medium text-slate-300">
              {tableTitle}
            </span>
          </div>
        )}
        <table className="min-w-max w-full text-xs font-mono">
          <thead className="bg-slate-800">
            <tr>
              {tableData.headers.map((header, i) => (
                <th
                  key={i}
                  className="whitespace-nowrap border-b border-slate-700 px-3 py-2 text-left font-medium text-slate-300"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableData.rows.map((row, i) => (
              <tr
                key={i}
                className={i % 2 === 0 ? "bg-slate-900/60" : "bg-slate-900/30"}
              >
                {tableData.headers.map((header, j) => (
                  <td
                    key={j}
                    className="whitespace-nowrap border-t border-slate-700/40 px-3 py-1.5 text-slate-400"
                  >
                    {String(row[header] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-300">
      {content}
    </pre>
  );
}
